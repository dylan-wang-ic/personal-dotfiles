# Ensure UTF-8 I/O for external CLI tools (Starship, Git, etc.)
[Console]::InputEncoding  = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

# ── PSReadLine ───────────────────────────────────────────────────────────────
Set-PSReadLineOption -PredictionSource HistoryAndPlugin
Set-PSReadLineOption -PredictionViewStyle InlineView
Set-PSReadLineOption -HistorySearchCursorMovesToEnd
Set-PSReadLineOption -BellStyle None
Set-PSReadLineOption -Colors @{
    InlinePrediction = "`e[38;5;242;3m"
}

Set-PSReadLineKeyHandler -Key UpArrow   -Function HistorySearchBackward
Set-PSReadLineKeyHandler -Key DownArrow -Function HistorySearchForward
Set-PSReadLineKeyHandler -Key Tab       -Function MenuComplete

# Ctrl = line, Alt = word. Alt+arrows move panes via Ctrl+Alt+arrows instead.
Set-PSReadLineKeyHandler -Key Ctrl+LeftArrow  -Function BeginningOfLine
Set-PSReadLineKeyHandler -Key Ctrl+RightArrow -Function EndOfLine
Set-PSReadLineKeyHandler -Key Alt+LeftArrow   -Function BackwardWord
Set-PSReadLineKeyHandler -Key Alt+RightArrow  -Function NextWord
Set-PSReadLineKeyHandler -Key Ctrl+Backspace  -Function DeleteLine
Set-PSReadLineKeyHandler -Key Alt+Backspace   -Function BackwardKillWord
Set-PSReadLineKeyHandler -Key Ctrl+Delete     -Function ForwardDeleteLine
Set-PSReadLineKeyHandler -Key Alt+Delete      -Function KillWord
Set-PSReadLineKeyHandler -Key Ctrl+z          -Function Undo

# ── Starship (single-spawn init + zero-fork transient prompt) ────────────────
if (Get-Command starship -ErrorAction SilentlyContinue) {
    function Invoke-Starship-TransientFunction {
        $glyph = [char]0x276F
        "`e[2;33m$glyph`e[0;33m$glyph`e[1;33m$glyph`e[0m "
    }
    Invoke-Expression ((& starship init powershell --print-full-init) -join "`n")
    Enable-TransientPrompt
}

# ── posh-git (lazy-loaded on first git/tgit/gitk Tab completion) ─────────────
Register-ArgumentCompleter -Native -CommandName git, tgit, gitk -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)

    Import-Module posh-git -Global -ErrorAction SilentlyContinue
    if (Get-Command Expand-GitCommand -ErrorAction SilentlyContinue) {
        $padLength = $cursorPosition - $commandAst.Extent.StartOffset
        $textToComplete = $commandAst.ToString().PadRight($padLength, ' ').Substring(0, $padLength)
        Expand-GitCommand $textToComplete
    }
}
