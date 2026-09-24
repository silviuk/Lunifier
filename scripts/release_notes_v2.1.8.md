# Lunifier 2.1.8 Release Notes

**Lunifier 2.1.8** delivers comprehensive size optimizations, zero-allocation ring buffer edge tracking, fast-path CPU skipping, visual theme brush synchronization, and runtime dependency checks across Windows and Linux.

---

### Highlights & Fixes in v2.1.8

#### 1. Size Optimizations & Codebase Cleanups
* **Removed Legacy Codebase**: Purged obsolete root Tkinter v1.x packages and stale build manifests, stripping over 6,100 lines of dead code and unreferenced assets.
* **Streamlined Dependencies**: Removed redundant `System.Text.Json` NuGet dependency from the Windows engine by leveraging the runtime's native assembly.
* **Stripped Debug Symbols**: Excluded `.pdb` symbol files from all distribution packages, saving user disk space and network bandwidth.
* **Reduced Final Footprints**: The Windows Inno Setup installer executable is reduced to **6.27 MB** and the MSIX package to **6.77 MB**.

#### 2. Performance & CPU Optimizations
* **Zero-Allocation Ring Buffer**: Replaced dynamic queue allocations in Windows `EdgeDetector.cs` with a pre-allocated 64-item ring buffer and reusable lock, eliminating GC pressure during mouse tracking.
* **Fast-Path Interior Bounding Box**: Screen collision logic now immediately skips all edge vector math whenever the mouse pointer is safely inside the screen interior.
* **Linux Process Spawning Hazard Removed**: Cached `xdotool` executable discovery to prevent repeated 15ms subprocess lookups.
* **Calibrated Cursor Repositioning**: Standardized inward cursor repositioning displacement to 60px across Windows and Linux, eliminating cursor jump jank while maintaining border bounceback prevention.

#### 3. Visual Polish & Dynamic Theming
* **Dynamic Version Resolution**: About and footer labels across Windows WPF and Linux Adwaita resolve the active version dynamically via reflection/package metadata.
* **Dynamic Theme Brush References**: Converted device lists and Bluetooth peer lists to `SetResourceReference`, ensuring instantaneous contrast updates when toggling between Windows Dark and Light modes.
* **Flexible Button Geometry**: Applied responsive minimum widths and symmetric padding to prevent button clipping.

#### 4. Packaging & Runtime Dependency Checks
* **.NET 9 Desktop Runtime Checker**: Inno Setup installer now verifies whether Microsoft .NET 9 Desktop Runtime (x64) is present. If missing, it prompts the user and offers to launch the official Microsoft download URL.
* **Enhanced Debian Package**: Updated Linux package metadata with `python3-evdev` and `bluez` recommendations, and configured the systemd user service to launch with `--minimized`.
* **Automated Test Suite**: Verified 100% pass rate across all 52 unit tests.

---

### Package Hashes (SHA-256)

| File | Size | SHA-256 Checksum |
| :--- | :--- | :--- |
| `Lunifier-Setup-2.1.8.exe` | 6.27 MB | `DB856741A6C4BCFC128843E40682404D006C5A24D2AE826B869B6CF91676487F` |
| `Lunifier-Windows-2.1.8.zip` | 6.73 MB | `C7B259D62AAF844B2A66FF602C181438EC07B5A88FE7DBACB35E08381641FEB0` |
| `Lunifier-2.1.8.0.msix` | 6.77 MB | `44236D03AD8D7DB527E70D47421CC9CE29940F30307A397EC991C4580F6AFFA7` |
| `lunifier_2.1.8_all.deb` | 173.5 KB | `4245532040253756299A79534899B8550016470368B73FFA6B6920C26A81FD86` |
| `Lunifier-Linux-2.1.8.tar.gz` | 243.3 KB | `392CCF8F752A1E97D5E251F106F296E653511A29B10DD25A92397299011BA091` |
