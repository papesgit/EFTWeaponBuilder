# EFT Weapon Builder

Blender addon for automatically importing, organizing, and texturing Escape From Tarkov weapon mods.  
Designed to streamline mod kitbashing, bone alignment, and material setup using a custom EFT shader (shader credits to @dvalinoff on youtube).

## 📦 Features

- Import weapons and mods from structured folders
- Attach mods using dropdown to correct bones
- Support for `weapon_compatibility.json` mapping
- Auto texture assignment using EFT Shader or Principled BSDF
- Bake Roughness maps directly in Blender using Python inversion

---

## 🧩 Installation

1. Download the latest `.zip` from the [Releases page](https://github.com/papesgit/EFTWeaponBuilder/releases)
2. Install it in Blender
3. Place `weapon_compatibility.json` in mods folder

---

## 🛠 Usage

1. Open the **EFT Mod Tool** panel in the 3D Viewport sidebar (press `N`)
2. Set the **Mods Folder** and **Weapons Folder** paths
3. Select a weapon and import it
4. Choose compatible mods via Weapon dropdown (incomplete, based on `weapon_compatibility.json`), filter or show all 
5. Select and import desired mods
6. Use **Build Bones from Empties** to convert FBX empties into bones
7. Select mod and weapon Armatures, hit refresh bone list and attach to desired bone.
8. Use **Auto Texture (EFT Shader)** to apply materials
9. Optionally, use **Bake Gloss → Roughness** to generate roughness maps

---

## 📤 Exporting Mods via AssetStudio

Use the included `mod_exporter.ps1` to export mods in the correct layout using AssetStudioMod CLI.

https://github.com/aelurum/AssetStudio/tree/AssetStudioMod/AssetStudioCLI

### ✍️ Setup

Edit the top of the script:

```powershell
$assetStudioCLI = "E:\PathToAssetStudio\AssetStudioModCLI_net8_portable\AssetStudioModCLI.exe"
$modsRoot = "E:\Path\To\Mods\Folder"
$outputRoot = "E:\Path\To\Mod_Export_Folder"
```
Then run the script in Powershell terminal.
