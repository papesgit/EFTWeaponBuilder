# === CONFIGURATION ===
$assetStudioCLI = "E:\PathToAssetStudio\AssetStudioModCLI_net8_portable\AssetStudioModCLI.exe"
$modsRoot = "E:\Path\To\Mods\Folder"
$outputRoot = "E:\Path\To\Mod_Export_Folder"

# === PROCESS EACH MOD CATEGORY ===
Get-ChildItem -Path $modsRoot -Directory | ForEach-Object {
    $modTypeName = $_.Name
    $modTypePath = $_.FullName
    $modOutputPath = Join-Path $outputRoot $modTypeName

    Write-Host "Exporting: $modTypeName"

    # Ensure output directory exists
    New-Item -ItemType Directory -Force -Path $modOutputPath | Out-Null

    # Run CLI in the same PowerShell window
    & $assetStudioCLI `
        "$modTypePath" `
        --mode splitObjects `
        --asset-type mesh,tex2d `
        --fbx-scale-factor 100 `
        --output "$modOutputPath"
}
