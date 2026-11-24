# Project Iris — Phase 1: Social Media UI Prototype for HakiOS

**Iris** is a modern social-media application designed and built for **HakiOS**, the experimental Darwin/XNU-based operating system port running on the **Samsung Galaxy A51** (Exynos 9611).

The application is built in native **Objective-C / UIKit** targeting ARM64 iOS 16.5 (`arm64-apple-ios16.5`), and is accompanied by a companion interactive simulator for visual verification.

---

## 1. Environment & Architecture Overview

### Target Device & System Metrics
* **Target Device:** Samsung Galaxy A51 (SM-A515F)
* **SoC:** Samsung Exynos 9611 (4x Cortex-A73 @ 1.45GHz + 4x Cortex-A53 @ 1.05GHz)
* **Kernel & OS:** Darwin / XNU (`xnu-8796.121.2`) on HakiOS
* **Userland Runtime:** iOS 16.5 (build 20F66) with `launchd`, `backboardd`, and `SpringBoard`
* **Display Resolution:** 1080 x 2400 pixels (Super AMOLED, 20:9 aspect ratio)
* **UIKit Viewport:** 360 x 800 points @ 3x display scale (`scale = 3.0`)
* **Status Bar:** Split status bar provider (`_UIStatusBarVisualProvider_Split1080`)
* **Touch Controller:** Melfas MSS100 I2C touchscreen driver (`hakios.a51input`)
* **GPU / Compositor:** SpringBoard backed by Mali Panfrost OpenGL ES 3.1 & CoreAnimation
* **Storage / Package Format:** Apple File System (APFS) container image (`iris.apfs`) mounted on `/private/preboot/apps`

### Design System & Color Palette
* **Dark Mode (Default & Primary):**
  * Main Background: `#0B0B0D`
  * Secondary Background: `#151518`
  * Card Background: `#1C1C20`
  * Primary Text: `#FFFFFF`
  * Secondary Text: `#A1A1AA`
  * Muted Text: `#71717A`
  * Accent Violet: `#8B5CF6`
  * Gradient Accent: `#8B5CF6` to `#EC4899`
  * Success: `#22C55E`
  * Error: `#EF4444`
* **Light Mode:**
  * Background: `#FAFAFA`
  * Secondary Background: `#FFFFFF`
  * Card Background: `#F4F4F5`
  * Primary Text: `#18181B`
  * Secondary Text: `#71717A`
* **Spacing:** 4px, 8px, 12px, 16px, 20px, 24px, 32px
* **Corner Radii:** Small: 8px, Medium: 12px, Large: 18px, Full: circular

---

## 2. Implemented Screens & Features

### Screen 1: Home Feed (`IrisFeedViewController`)
* **Top Navigation Bar:**
  * Iris wordmark in bold typography with radiant violet gradient dot.
  * Theme switcher button (live dark/light mode toggle).
  * Activity/Notifications shortcut button.
  * Direct Messages shortcut button with informative Phase 2 modal.
* **Stories Section (`IrisStoriesHeaderView`):**
  * Horizontal scrolling row with "Your Story" plus badge.
  * 10 realistic mock users (alex, maya, jordan, sara, dev, arjun, emily, noah, clara, liam).
  * Glowing gradient ring (`#8B5CF6` to `#EC4899`) around unread stories; muted border for viewed stories.
  * Tapping any story opens the Fullscreen Story Viewer.
* **Feed Posts (`IrisPostCell`):**
  * Vertically scrolling feed with 10 detailed mock photography posts.
  * Header with circular avatar, tappable username, location label, and three-dot options menu.
  * Large photographic media with aspect-ratio preservation (square 1:1, portrait 4:5/1.25) and rounded corners.
  * Interactive action bar: Like (with animated bounce and counter update), Comments, Share sheet, and Bookmark toggle.
  * Rich metadata: like count, bold username + caption, hashtags, "View all N comments" preview, and relative timestamps.
  * Full local state: likes and bookmarks persist across screen transitions.

### Screen 2: Explore (`IrisExploreViewController`)
* Header with "Explore" title and responsive search bar with magnifying glass icon.
* Real-time local search filtering posts by username, caption, hashtags, and location.
* Dynamic masonry grid supporting square tiles, tall portrait cards, wide featured hero banners, and video cards with play icon badge.
* Tapping any explore tile opens the Fullscreen Post Viewer.

### Screen 3: Create (`IrisCreateViewController`)
* Clean creation workflow without touching hardware sensors directly.
* Media preview box with procedural photographic art.
* Mock buttons for Gallery selection and Camera sensor capture.
* Multiline caption input text view with placeholder behavior.
* Location input field.
* Audience selector pills: "Public", "Close Friends", "Private".
* Prominent "Share to Iris Feed" gradient action button: adds the newly created post to the top of the feed, notifies the user, and automatically navigates to the Home feed.

### Screen 4: Activity (`IrisActivityViewController`)
* Notification feed supporting 4 distinct types: Likes, Follows, Comments, and Mentions.
* Circular user avatars, bold highlighted usernames, and relative timestamps.
* Post media thumbnails for post-related activities (tapping thumbnail opens the post).
* Interactive Follow/Following toggle button with live state updates.
* Tapping a user navigates directly to their profile.

### Screen 5: Profile (`IrisProfileViewController`)
* Support for multiple user profiles (alex, maya, jordan, sara, dev, emily).
* Profile header with 76x76 avatar, gradient border, post count, followers count, and following count.
* Bio, display name, and clickable website link.
* Dynamic action buttons: "Edit Profile" (interactive name & bio editor) and "Share Profile" for the current user; "Follow/Following" toggle and "Message" for external users.
* Content tabs: Posts Grid, Reels, and Tagged Posts.
* 3x3 photo grid (at least 9 mock photos per profile) with tap-to-view interaction.
* Settings gear icon in top navigation bar opening the Settings screen.

### Screen 6: Fullscreen Post Viewer (`IrisPostViewerViewController`)
* Clean edge-to-edge media presentation on dark backdrop.
* User avatar, username, location, like count, and caption overlay.
* Interactive action bar: Like, Comment, Share, Bookmark.
* Swipe navigation: swipe left for next post, swipe right for previous post, swipe down to dismiss.

### Screen 7: Comments (`IrisCommentsViewController`)
* Modal comments sheet displaying threaded comments with avatars, usernames, and timestamps.
* Comment like heart buttons with state toggles.
* Bottom input field with "Post" button allowing users to type and publish new comments immediately into local state.

### Screen 8: Settings (`IrisSettingsViewController`)
* Accessible from user profile.
* Appearance section: live Dark Mode / Light Mode toggle switch.
* HakiOS Runtime & Performance section: Display resolution (1080x2400 @ 3x), target framerate (60 FPS / 9.4 ms frame time), compositor (SpringBoard / Mali Panfrost), and input subsystem (Melfas MSS100).
* About Iris section: Version 1.0.0-hakios (Phase 1 UI Prototype).

### Persistent Bottom Navigation Bar (`IrisTabBarController`)
* Persistent 5-tab navigation: Home, Explore, Create, Activity, Profile.
* Minimum 44x44 pt touch targets.
* Custom vector iconography with active state highlights and sliding violet indicator pill.
* Preserves state between tab switches.

---

## 3. Project File Structure

```
apps/Iris/
├── build.sh                               # Automated build, signing & APFS packaging script
├── resources/
│   └── Info.plist                         # App bundle configuration & URL scheme (iris://)
├── src/
│   ├── AppDelegate.h / .m                 # App lifecycle, UIWindow & root tab bar setup
│   ├── IrisActivityViewController.h / .m  # Activity & notifications screen
│   ├── IrisCommentsViewController.h / .m  # Comments list & local comment posting
│   ├── IrisCreateViewController.h / .m    # Post creation interface
│   ├── IrisData.h / .m                    # Centralized mock data models & offline artwork engine
│   ├── IrisExploreViewController.h / .m   # Explore screen with live search & dynamic grid
│   ├── IrisFeedViewController.h / .m      # Home feed with stories row & post components
│   ├── IrisPostCell.h / .m                # Reusable post table cell
│   ├── IrisPostViewerViewController.h / .m# Fullscreen post viewer with swipe navigation
│   ├── IrisProfileViewController.h / .m   # Profile screen with 3x3 grid & user switcher
│   ├── IrisSettingsViewController.h / .m  # Settings & HakiOS performance diagnostics
│   ├── IrisStoriesHeaderView.h / .m       # Horizontal stories row with gradient rings
│   ├── IrisStoryViewerViewController.h / .m# Fullscreen story viewer with progress bar
│   ├── IrisTabBarController.h / .m        # Persistent bottom tab bar controller
│   ├── IrisTheme.h / .m                   # Central design system & dark/light theme engine
│   ├── IrisTopNavBar.h / .m               # Top navigation bar with theme toggle & shortcuts
│   └── main.m                             # Entry point (UIApplicationMain)
└── web/
    └── index.html                         # Interactive Samsung Galaxy A51 UI simulator
```

---

## 4. Build Instructions

### Prerequisites
* Windows Subsystem for Linux (WSL) with `A51-KernelBuilder` distribution.
* Theos toolchain at `/opt/a51-hakios/theos` with `iPhoneOS16.5.sdk`.
* Clang cross-compiler wrapper `xnu-clang` and Mach-O signer `ldid`.

### Building Native ARM64 Mach-O `Iris.app` & `iris.apfs`
Run the build script from PowerShell or Bash:
```powershell
wsl.exe -d A51-KernelBuilder bash -c "/mnt/c/Users/Ankit/Desktop/A51/hakios-a51/apps/Iris/build.sh"
```

The script will:
1. Compile all Objective-C sources targeting `arm64-apple-ios16.5` with ARC and `-O2` optimizations.
2. Link against `UIKit`, `Foundation`, `CoreGraphics`, and `QuartzCore`.
3. Package the application bundle at `apps/Iris/build/Iris.app/`.
4. Sign the Mach-O binary using `ldid -S`.
5. Stage the application in `/opt/a51-hakios/apps/Payload/Iris.app`.
6. Package the application into an APFS image container `iris.apfs` using `mkapfs.py`.

---

## 5. Launching on HakiOS

Once booted into HakiOS with SpringBoard active:

1. **Mount the Apps APFS Container (if booted with external app partition):**
   ```bash
   mount -t apfs /dev/ufs_prism /private/preboot/apps
   ```
2. **Register Iris with LaunchServices:**
   ```bash
   /redwood/bin/uicache -p /private/preboot/apps/Iris.app
   ```
   *(This registers `com.hakios.iris` and places the Iris icon on SpringBoard's home screen.)*
3. **Launch Iris via SpringBoard:**
   * Either tap the **Iris** icon on the SpringBoard home screen, or
   * Launch via URL scheme from terminal:
     ```bash
     /redwood/bin/uiopen iris://
     ```
     *(Or directly to a specific tab: `/redwood/bin/uiopen iris://explore`, `iris://create`, `iris://activity`, `iris://profile`)*

---

## 6. Testing & Visual Verification

### Native Mach-O Build Verification
* **Binary Type:** `Mach-O 64-bit arm64 executable, flags:<NOUNDEFS|DYLDLINK|TWOLEVEL|PIE>`
* **Binary Size:** ~375 KB (lean, zero bloated frameworks, optimized for memory-constrained HakiOS environments)
* **APFS Container:** `iris.apfs` verified cleanly by `apfs.py` with 1 volume ("Apps"), block size 4096.

### Interactive Visual Verification
Open [`apps/Iris/web/index.html`](web/index.html) in any modern browser to interact with the complete application inside the Samsung Galaxy A51 viewport:
* Test live theme switching between Dark and Light mode.
* Scroll through stories and tap to view fullscreen stories with left/right tap navigation.
* Like posts and observe the animated heart bounce and live like counters.
* Open comments, browse discussions, and submit new comments in real time.
* Filter explore posts in real time using the search field.
* Create a new post, select photos, and share it to see it appear immediately at the top of the feed.
* View profiles, toggle follow states, edit bio and display name, and inspect performance diagnostics.
