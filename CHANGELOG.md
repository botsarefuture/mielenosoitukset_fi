# Changelog

## v3.0.0 – **Evolution Edition** 🚀
 
### 🌟 New Features
- **Redesigned UI**: Implemented a new responsive layout with an improved grid system and refined color themes.
- **Enhanced Field Naming**: Updated all field names to use underscore formatting for consistency.
 
### 🛠️ Fixes
- **Critical Crash Fixes**: Resolved issues causing app crashes during profile picture uploads and improved data synchronization.
 
### ✨ Updates
- **Performance Optimization**: Migrated legacy features and optimized module interactions.
- **Deprecation Guidelines Update**: Revised deprecation guidelines to align with the latest project standards.

## v2.9.2 – **The Bug Squashing Edition** 🌟

### 🛠️ Fixes
- **Critical Bug Fix**: Resolved an issue causing app crashes during profile picture uploads.
- **Minor Bug Fixes**: Addressed various small bugs affecting app behavior.


## v2.8.6 – **The Organization Enhancement Edition** 🌟

### 🌟 New Features
- **API Endpoint for Organizations**: Added a new API endpoint to create new organizations.

### ✨ Updates
- **Organization Insertion Logic**: Enhanced the logic for inserting organizations to ensure data integrity.
- **Admin Interface**: Updated the admin interface to support the new organization creation feature.

## v2.8.5 – **The Organizer Fix Edition** 🌟

### 🛠️ Fixes
- **Organization ID Assignment**: Fixed the `fix_organizers` function to handle `None` values properly.


## v2.8.4 – **The Modernization Edition** 🌟

### ✨ Updates
- **Flask Versioning**: Updated Flask to the latest version for improved security and performance.
- **Dependency Management**: Upgraded all dependencies to their latest versions.
- **Documentation Overhaul**: Removed outdated documentation and added comprehensive guides for new features.
- **Codebase Cleanup**: Refactored code to remove deprecated methods and improve readability.

---  

## v2.8.3 – **The Structural Overhaul Edition** 🌟

### ✨ Updates
- **Project Structure**: Refactored project structure by removing unused files, adding new modules, and updating versioning.
- **Email Templates**: Enhanced email templates for better user engagement.
- **JavaScript Functionality**: Improved JavaScript functionality for a smoother user experience.

---  

## v2.8.2 – **The Polished Performance Edition** 🌟  

### 🚫 Deprecations  
- **Leaflet Attribution Control**: Deprecated method for hiding Leaflet attribution control.  

### ✨ Updates  
- **Logging Level**: Updated logging level for recurring demonstrations.  
- **Type Checking**: Improved type checking in the Demonstration class.  
- **Documentation**: Enhanced script documentation and copyright notice.  

---  

## v2.8.1 – **The Sparkly Bug Fix Edition** 🌟  

### 🛠️ Fixes  
- **Critical Bug Fix**: Resolved an issue causing app crashes during profile picture uploads.  
- **Minor Bug Fixes**: Addressed various small bugs affecting app behavior.  

### ✨ Updates  
- **Dependency Updates**: Upgraded to the latest versions to enhance performance and security.  

### 🚫 Deprecations  
- **Feature Removals**: Discontinued outdated functionalities no longer in use.  

---  

## v2.8.0 – **The Ultimate Glow-Up Edition** 🌟  

### 🌟 New Features  
- **Enhanced User Profiles**: Introduced custom avatars, profile themes, and animations.  
- **Advanced Role Management**: Create and assign unique roles with a personalized flair.  
- **Smart Notifications**: Added emojis, sound effects, and custom notification settings.  
- **AI-Driven Personalization**: Seamless customization based on user preferences.  
- **One-Click Settings Sync**: Sync settings across devices effortlessly.  
- **Enhanced Privacy**: Improved data security measures for top-notch confidentiality.  
- **Guardian Mode**: Detect and neutralize threats automatically.  

### 🛠️ Fixes  
- **Improved Sync Performance**: Eliminated delays in data synchronization.  
- **Crash-Free Startup**: Enhanced app stability for a smoother experience.  

### ✨ Updates  
- **Dependency Optimization**: Leveraged next-gen versions for improved functionality.  
- **Performance Boost**: Streamlined app operations for faster, more efficient use.  

---  

## v2.7.0 – **The Navigator’s Dream** 🌟  

### 🌟 New Features  
- **Language Navigation 2.0**: Now includes immersive and comprehensive translation capabilities.  

---  

## v2.6.0 – **The Foundation for Greatness** 🌟  

### 🌟 New Features  
- **Advanced Authentication**: Added new user login features, including face recognition.  
- **Fortress-Level Encryption**: Reinforced data security with cutting-edge encryption.  
- **UI Enhancements**: Subtle design updates for a cleaner and more vibrant interface.  
- **Universal Language Support**: Expanded support for multiple languages and emojis.  

### 🛠️ Fixes  
- **Faster Data Syncing**: Optimized for quicker and more reliable synchronization.  
- **Crash Resistance**: Improved stability under high-load scenarios.  

### ✨ Updates  
- **Dependency Improvements**: Upgraded backend components for scalability.  
- **Code Refinement**: Enhanced codebase efficiency for improved performance.  

---  

## [Unreleased]
### Added
- Email notification to tuki@mielenosoitukset.fi when a new demonstration is submitted (uses underscore field names, numpydoc docstrings).
- User can subscribe to demonstration reminders (muistutus) via email; reminders are sent 1 week before, the day before at 9:00, and the day of at 9:00 or at least 2 hours before the event.
- Reminder subscription form as a popup/modal, styled for light/dark mode and always visible above the header.
- All popups and modals use z-index above the header (1000001 for backdrop, 1000002 for modal) codebase-wide.
- All main CSS and button styles use color variables and light-dark() for full theme support.

### Changed
- UI containers and popups have improved contrast, spacing, and a cleaner look in both light and dark modes.
- All buttons have visible background and border in all color modes.
- Reminder subscribe button is grouped with social/share buttons.

### Fixed
- Modals/popups are never hidden behind the header.
- Removed visible borders from stacked containers for a cleaner UI.

Enjoy a more secure, efficient, and polished experience! 🚀