# pyvterm shell integration for PowerShell (5.1 and 7+)
#  - OSC 133 command blocks (prompt / command / output / exit code)
#  - OSC 7 + OSC 9;9 current directory (new tabs & splits open in the same folder)
# pyvterm dot-sources this automatically. Manual use (e.g. in $PROFILE):
#   if ($env:TERM_PROGRAM -eq 'pyvterm') { . 'C:\path\to\pyvterm\shell\pyvterm.ps1' }
if ($global:__pyvterm_loaded) { return }
$global:__pyvterm_loaded = $true
$global:__pyvterm_orig_prompt = $function:prompt
$global:__pyvterm_first = $true

function global:prompt {
    $ok = $?
    $code = 0
    if (-not $ok) { $code = if ($global:LASTEXITCODE) { $global:LASTEXITCODE } else { 1 } }
    $e = [char]27; $b = [char]7
    $out = ''
    if (-not $global:__pyvterm_first) { $out += "$e]133;D;$code$b" }
    $global:__pyvterm_first = $false
    $loc = $executionContext.SessionState.Path.CurrentLocation
    if ($loc.Provider.Name -eq 'FileSystem') {
        $p = $loc.ProviderPath
        $out += "$e]9;9;`"$p`"$b"
        $out += "$e]7;file://$($env:COMPUTERNAME)/$($p -replace '\\','/')$b"
    }
    $out += "$e]133;A$b"
    $out += & $global:__pyvterm_orig_prompt
    $out += "$e]133;B$b"
    return $out
}

# mark "command executed" right after Enter (needs PSReadLine, default in PS 5.1+)
if (Get-Module PSReadLine) {
    Set-PSReadLineKeyHandler -Key Enter -BriefDescription 'pyvterm-accept' -ScriptBlock {
        [Microsoft.PowerShell.PSConsoleReadLine]::AcceptLine()
        [Console]::Write("$([char]27)]133;C$([char]7)")
    }
}
