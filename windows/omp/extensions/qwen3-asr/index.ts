/**
 * Qwen3-ASR as omp's `dictation` model, owned entirely by omp: no manual server, no login item.
 *
 * While an interactive omp is open this extension serves an OpenAI-style
 * `/v1/audio/transcriptions` endpoint on 127.0.0.1:8765 and registers it as the speech-to-text model
 * `local-asr/qwen3-asr-0.6b`. The heavy part (server.py: torch + the model, ~2 GiB GPU and RAM) is spawned
 * on the first transcription and stopped after IDLE_MS without one, and with omp. Run setup.py once per
 * machine to create the Python environment; this extension offers to do that when it is missing.
 */
import { type ChildProcess, spawn } from "node:child_process";
import { closeSync, existsSync, mkdirSync, openSync } from "node:fs";
import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import { createServer as createNetServer } from "node:net";
import { homedir } from "node:os";
import { join } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";

const PORT = 8765;
const MODEL_ID = "qwen3-asr-0.6b";
const IDLE_MS = 15 * 60_000; // same window as omp's own local workers
const START_TIMEOUT_MS = 180_000;
const FORWARD_TIMEOUT_MS = 300_000;
const MAX_BODY_BYTES = 26 * 1024 * 1024;

const HOME = join(homedir(), ".omp");
const EXT_DIR = join(HOME, "agent", "extensions", "qwen3-asr");
const ENV_DIR = join(HOME, "qwen3-asr");
const PYTHON = join(ENV_DIR, "venv", "Scripts", "python.exe");
const WORKER_LOG = join(ENV_DIR, "worker.log");
const SETUP_LOG = join(ENV_DIR, "setup.log");
const PY_LAUNCHER = ["py", "-3"]; // Windows-only extension

type Ctx = {
	mode?: string;
	hasUI?: boolean;
	agent?: { kind?: string };
	ui: { notify: (message: string, level?: string) => void; confirm: (title: string, message: string) => Promise<boolean> };
	setInterval: (fn: () => void, ms: number) => unknown;
};
type Pi = {
	on: (event: string, handler: (event: unknown, ctx: Ctx) => unknown) => void;
	registerProvider: (name: string, config: Record<string, unknown>) => void;
	logger?: { warn?: (message: string) => void };
};

// Module state is shared by every session in the process, so it is guarded rather than per-session.
let server: Server | undefined;
let worker: ChildProcess | undefined;
let workerPort = 0;
let workerReady = false;
let starting: Promise<void> | undefined;
let inflight = 0;
let lastDone = Date.now();
let owner = false; // true while a main interactive session runs the endpoint
let setupRunning = false;

function freePort(): Promise<number> {
	const { promise, resolve, reject } = Promise.withResolvers<number>();
	const probe = createNetServer();
	probe.once("error", reject);
	probe.listen(0, "127.0.0.1", () => {
		const address = probe.address();
		probe.close(() => (address && typeof address === "object" ? resolve(address.port) : reject(new Error("no port"))));
	});
	return promise;
}

async function workerHealthy(port: number): Promise<boolean> {
	try {
		const res = await fetch(`http://127.0.0.1:${port}/health`, { signal: AbortSignal.timeout(1500) });
		const body: unknown = await res.json();
		return typeof body === "object" && body !== null && "status" in body && body.status === "ok";
	} catch {
		return false;
	}
}

/** Kill the whole tree: the venv python.exe is a launcher that starts the real interpreter as a child. */
function stopWorker(): void {
	const pid = worker?.pid;
	worker = undefined;
	workerReady = false;
	if (pid) spawn("taskkill", ["/PID", String(pid), "/T", "/F"], { stdio: "ignore", windowsHide: true }).unref();
}

async function startWorker(): Promise<void> {
	workerPort = await freePort();
	mkdirSync(ENV_DIR, { recursive: true });
	const log = openSync(WORKER_LOG, "a");
	const child = spawn(PYTHON, [join(EXT_DIR, "server.py")], {
		env: {
			...process.env,
			QWEN_ASR_PORT: String(workerPort),
			QWEN_ASR_PARENT_PID: String(process.pid),
			HF_HUB_OFFLINE: "1", // weights come from the local cache that setup.py filled
		},
		stdio: ["ignore", log, log],
		windowsHide: true,
	});
	closeSync(log);
	worker = child;
	child.once("exit", () => {
		if (worker === child) {
			worker = undefined;
			workerReady = false;
		}
	});
	const deadline = Date.now() + START_TIMEOUT_MS;
	while (Date.now() < deadline) {
		if (child.exitCode !== null) throw new Error(`worker exited while starting (see ${WORKER_LOG})`);
		if (await workerHealthy(workerPort)) {
			workerReady = true;
			return;
		}
		await sleep(250);
	}
	stopWorker();
	throw new Error("worker start timed out");
}

function ensureWorker(): Promise<void> {
	if (worker && workerReady && worker.exitCode === null) return Promise.resolve();
	starting ??= startWorker().finally(() => {
		starting = undefined;
	});
	return starting;
}

function readBody(req: IncomingMessage): Promise<Buffer> {
	const { promise, resolve, reject } = Promise.withResolvers<Buffer>();
	const chunks: Buffer[] = [];
	let size = 0;
	req.on("data", (chunk: Buffer) => {
		size += chunk.length;
		if (size > MAX_BODY_BYTES) {
			reject(new Error("request body too large"));
			req.destroy();
			return;
		}
		chunks.push(chunk);
	});
	req.on("end", () => resolve(Buffer.concat(chunks)));
	req.on("error", reject);
	return promise;
}

function json(res: ServerResponse, status: number, body: unknown): void {
	const text = JSON.stringify(body);
	res.writeHead(status, { "content-type": "application/json", "content-length": Buffer.byteLength(text) });
	res.end(text);
}

async function handle(req: IncomingMessage, res: ServerResponse): Promise<void> {
	try {
		if (req.method === "GET" && req.url === "/health") {
			return json(res, 200, { status: "ok", model: MODEL_ID, worker: worker && workerReady ? "running" : "idle" });
		}
		if (req.method === "GET" && req.url === "/v1/models") {
			return json(res, 200, { object: "list", data: [{ id: MODEL_ID, object: "model", owned_by: "local" }] });
		}
		if (req.method !== "POST" || req.url !== "/v1/audio/transcriptions") return json(res, 404, { detail: "not found" });

		const body = await readBody(req);
		inflight++;
		try {
			await ensureWorker();
			const upstream = await fetch(`http://127.0.0.1:${workerPort}/v1/audio/transcriptions`, {
				method: "POST",
				headers: { "content-type": String(req.headers["content-type"] ?? "application/octet-stream") },
				body,
				signal: AbortSignal.timeout(FORWARD_TIMEOUT_MS),
			});
			const out = Buffer.from(await upstream.arrayBuffer());
			res.writeHead(upstream.status, {
				"content-type": upstream.headers.get("content-type") ?? "application/json",
				"content-length": out.length,
			});
			res.end(out);
		} finally {
			inflight--;
			lastDone = Date.now();
		}
	} catch (error) {
		if (res.headersSent) res.end();
		else json(res, 503, { detail: `ASR worker unavailable: ${String(error)}` });
	}
}

/** Bind the endpoint. Resolves quietly when another omp window already serves it; the tick retries. */
function listen(): Promise<void> {
	const { promise, resolve } = Promise.withResolvers<void>();
	const candidate = createServer((req, res) => void handle(req, res));
	candidate.once("error", () => resolve()); // EADDRINUSE: another omp owns the port for now
	candidate.listen(PORT, "127.0.0.1", () => {
		candidate.on("error", () => {});
		candidate.unref();
		server = candidate;
		resolve();
	});
	return promise;
}

/** Environment missing (new machine or reinstall): offer the one-time install instead of failing silently. */
async function offerSetup(ctx: Ctx): Promise<void> {
	if (setupRunning) return;
	const setup = join(EXT_DIR, "setup.py");
	const ok = await ctx.ui.confirm(
		"Qwen3-ASR dictation",
		"The Python environment for the Qwen3-ASR dictation model is not installed on this machine (about 6 GB: " +
			"PyTorch + the model). Install it now? Until then dictation falls back to local Whisper.",
	);
	if (!ok) {
		ctx.ui.notify(`Skipped. Install later with: ${PY_LAUNCHER.join(" ")} "${setup}"`, "info");
		return;
	}
	setupRunning = true;
	mkdirSync(ENV_DIR, { recursive: true });
	const log = openSync(SETUP_LOG, "w");
	const [cmd, ...args] = PY_LAUNCHER;
	const child = spawn(cmd, [...args, setup], { stdio: ["ignore", log, log], windowsHide: true });
	closeSync(log);
	ctx.ui.notify(`Installing Qwen3-ASR in the background (log: ${SETUP_LOG}).`, "info");
	child.once("error", error => {
		setupRunning = false;
		ctx.ui.notify(`Qwen3-ASR install could not start: ${String(error)}`, "error");
	});
	child.once("exit", code => {
		setupRunning = false;
		if (code === 0) ctx.ui.notify("Qwen3-ASR is installed. Dictation will use it from now on.", "info");
		else ctx.ui.notify(`Qwen3-ASR install failed (exit ${code}). See ${SETUP_LOG}.`, "error");
	});
}

export default function (pi: Pi) {
	pi.registerProvider("local-asr", {
		baseUrl: `http://127.0.0.1:${PORT}/v1`,
		apiKey: "not-needed",
		models: [
			{
				id: MODEL_ID,
				name: "Qwen3-ASR 0.6B (local)",
				api: "openai-transcriptions",
				reasoning: false,
				input: ["text"],
				cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
				contextWindow: 128000,
				maxTokens: 16384,
			},
		],
	});

	pi.on("session_start", async (_event, ctx) => {
		try {
			// Only the main interactive session runs the endpoint; print/rpc runs and subagents must not.
			if (!ctx.hasUI || ctx.mode !== "tui" || ctx.agent?.kind === "sub" || owner) return;
			owner = true;
			if (!existsSync(PYTHON)) void offerSetup(ctx);
			await listen();
			ctx.setInterval(() => {
				try {
					if (!server) void listen(); // take over if the omp window that held the port has closed
					if (worker && inflight === 0 && Date.now() - lastDone > IDLE_MS) stopWorker();
				} catch (error) {
					pi.logger?.warn?.(`qwen3-asr tick failed: ${String(error)}`);
				}
			}, 10_000);
		} catch (error) {
			pi.logger?.warn?.(`qwen3-asr start failed: ${String(error)}`);
		}
	});

	pi.on("session_shutdown", (_event, ctx) => {
		if (ctx.agent?.kind === "sub" || !owner) return;
		owner = false;
		server?.close();
		server = undefined;
		stopWorker();
	});
}
