#!/bin/bash
#
# KDE-LogiWheel Installation Script
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  KDE-LogiWheel Installation Script${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}Please do not run as root. The script will ask for sudo when needed.${NC}"
    exit 1
fi

# Detect package manager
detect_package_manager() {
    if command -v pacman &> /dev/null; then
        echo "pacman"
    elif command -v apt &> /dev/null; then
        echo "apt"
    elif command -v dnf &> /dev/null; then
        echo "dnf"
    elif command -v zypper &> /dev/null; then
        echo "zypper"
    else
        echo "unknown"
    fi
}

PKG_MANAGER=$(detect_package_manager)
echo -e "Detected package manager: ${GREEN}${PKG_MANAGER}${NC}"

# Install dependencies
echo ""
echo -e "${YELLOW}Installing dependencies...${NC}"

case $PKG_MANAGER in
    pacman)
        sudo pacman -S --needed python python-pip python-pyqt6 python-dbus xdotool
        # Optional: logiops for Logitech mouse support
        if ! command -v logid &> /dev/null; then
            echo -e "${YELLOW}Would you like to install logiops for Logitech mouse support? [y/N]${NC}"
            read -r response
            if [[ "$response" =~ ^[Yy]$ ]]; then
                sudo pacman -S --needed logiops
            fi
        fi
        ;;
    apt)
        sudo apt update
        sudo apt install -y python3 python3-pip python3-pyqt6 python3-dbus xdotool
        ;;
    dnf)
        sudo dnf install -y python3 python3-pip python3-qt6 python3-dbus xdotool
        ;;
    zypper)
        sudo zypper install -y python3 python3-pip python3-qt6-devel python3-dbus-python xdotool
        ;;
    *)
        echo -e "${RED}Unknown package manager. Please install dependencies manually:${NC}"
        echo "  - Python 3.10+"
        echo "  - PyQt6"
        echo "  - dbus-python"
        echo "  - xdotool (for X11)"
        echo "  - pynput or python-evdev (optional, for input detection)"
        ;;
esac

# Install Python package
echo ""
echo -e "${YELLOW}Installing KDE-LogiWheel...${NC}"

pip install --user -e .

# Install optional dependencies
echo ""
echo -e "${YELLOW}Installing optional dependencies for input handling...${NC}"
pip install --user pynput evdev 2>/dev/null || true

# Install desktop entries
echo ""
echo -e "${YELLOW}Installing desktop entries...${NC}"

# Application entry
mkdir -p ~/.local/share/applications
cp data/org.kde.logiwheel.desktop ~/.local/share/applications/

# Autostart entry
mkdir -p ~/.config/autostart
cp data/org.kde.logiwheel.autostart.desktop ~/.config/autostart/

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database ~/.local/share/applications
fi

# Add user to input group (for evdev access on Wayland)
echo ""
echo -e "${YELLOW}Adding user to 'input' group for input device access...${NC}"
echo -e "${YELLOW}You may need to log out and back in for this to take effect.${NC}"
sudo usermod -aG input "$USER" 2>/dev/null || true

# Create default config
echo ""
echo -e "${YELLOW}Creating default configuration...${NC}"
python3 -c "from src.config import ConfigManager; ConfigManager().load()" 2>/dev/null || true

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Installation Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "To start KDE-LogiWheel:"
echo "  1. Run the daemon: kde-logiwheel-daemon"
echo "  2. Or use the systemd service: systemctl --user enable --now kde-logiwheel"
echo ""
echo "To configure:"
echo "  - Run: kde-logiwheel-config"
echo "  - Or find 'KDE LogiWheel' in your application menu"
echo ""
echo "Default trigger: Super+Alt+W (hold to show wheel)"
echo ""
echo "For Logitech mouse integration, see the README for logid setup."
echo ""
