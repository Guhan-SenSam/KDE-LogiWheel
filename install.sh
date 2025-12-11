#!/bin/bash
#
# KDE-LogiWheel Installation Script
# Installs into an isolated virtual environment
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Installation directory
INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/kde-logiwheel"
VENV_DIR="$INSTALL_DIR/venv"
BIN_DIR="$HOME/.local/bin"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  KDE-LogiWheel Installation Script${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Installation directory: ${BLUE}$INSTALL_DIR${NC}"
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

# Install system dependencies
echo ""
echo -e "${YELLOW}Installing system dependencies...${NC}"

case $PKG_MANAGER in
    pacman)
        sudo pacman -S --needed python python-pip python-virtualenv xdotool
        # Check for PyQt6 - might need AUR
        if ! pacman -Qi python-pyqt6 &> /dev/null; then
            echo -e "${YELLOW}PyQt6 will be installed via pip in the virtual environment${NC}"
        fi
        ;;
    apt)
        sudo apt update
        sudo apt install -y python3 python3-pip python3-venv python3-dbus xdotool
        # PyQt6 often needs to be installed via pip on Debian/Ubuntu
        ;;
    dnf)
        sudo dnf install -y python3 python3-pip python3-virtualenv python3-dbus xdotool
        ;;
    zypper)
        sudo zypper install -y python3 python3-pip python3-virtualenv python3-dbus-python xdotool
        ;;
    *)
        echo -e "${YELLOW}Unknown package manager. Please ensure these are installed:${NC}"
        echo "  - Python 3.10+"
        echo "  - python3-venv or python3-virtualenv"
        echo "  - xdotool"
        ;;
esac

# Optional: Install logiops for Logitech mouse support
if ! command -v logid &> /dev/null; then
    echo ""
    echo -e "${YELLOW}Would you like to install logiops for Logitech mouse support? [y/N]${NC}"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        case $PKG_MANAGER in
            pacman) sudo pacman -S --needed logiops ;;
            apt) sudo apt install -y logiops 2>/dev/null || echo "logiops not in repos, install manually" ;;
            dnf) sudo dnf install -y logiops 2>/dev/null || echo "logiops not in repos, install manually" ;;
            *) echo "Please install logiops manually" ;;
        esac
    fi
fi

# Create installation directory
echo ""
echo -e "${YELLOW}Creating installation directory...${NC}"
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"

# Copy source files
echo -e "${YELLOW}Copying source files...${NC}"
cp -r "$(dirname "$0")/src" "$INSTALL_DIR/"
cp "$(dirname "$0")/pyproject.toml" "$INSTALL_DIR/"
cp "$(dirname "$0")/requirements.txt" "$INSTALL_DIR/"
cp "$(dirname "$0")/setup.py" "$INSTALL_DIR/" 2>/dev/null || true

# Create virtual environment
echo ""
echo -e "${YELLOW}Creating virtual environment...${NC}"
python3 -m venv "$VENV_DIR"

# Activate and install dependencies
echo -e "${YELLOW}Installing Python dependencies in virtual environment...${NC}"
source "$VENV_DIR/bin/activate"

# Upgrade pip
pip install --upgrade pip

# Install the package and dependencies
pip install -e "$INSTALL_DIR"

# Install optional input handling dependencies
echo -e "${YELLOW}Installing optional input handling libraries...${NC}"
pip install pynput evdev 2>/dev/null || echo -e "${YELLOW}Some optional deps failed (may need system libs)${NC}"

deactivate

# Create wrapper scripts
echo ""
echo -e "${YELLOW}Creating executable scripts...${NC}"

# Main daemon script
cat > "$BIN_DIR/kde-logiwheel-daemon" << 'WRAPPER'
#!/bin/bash
INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/kde-logiwheel"
source "$INSTALL_DIR/venv/bin/activate"
exec python -m src.service.daemon "$@"
WRAPPER
chmod +x "$BIN_DIR/kde-logiwheel-daemon"

# Config UI script
cat > "$BIN_DIR/kde-logiwheel-config" << 'WRAPPER'
#!/bin/bash
INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/kde-logiwheel"
source "$INSTALL_DIR/venv/bin/activate"
exec python -m src.ui.main_window "$@"
WRAPPER
chmod +x "$BIN_DIR/kde-logiwheel-config"

# Main CLI script
cat > "$BIN_DIR/kde-logiwheel" << 'WRAPPER'
#!/bin/bash
INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/kde-logiwheel"
source "$INSTALL_DIR/venv/bin/activate"
exec python -m src "$@"
WRAPPER
chmod +x "$BIN_DIR/kde-logiwheel"

# Install desktop entries
echo ""
echo -e "${YELLOW}Installing desktop entries...${NC}"

# Application entry
mkdir -p ~/.local/share/applications
cat > ~/.local/share/applications/org.kde.logiwheel.desktop << EOF
[Desktop Entry]
Type=Application
Name=KDE LogiWheel
GenericName=Shortcut Wheel
Comment=A Logitech-style shortcut wheel for KDE
Icon=input-mouse
Exec=$BIN_DIR/kde-logiwheel-config
Terminal=false
Categories=Qt;KDE;Settings;HardwareSettings;
Keywords=logitech;mouse;wheel;shortcut;radial;menu;
StartupNotify=true
X-KDE-StartupNotify=true
EOF

# Autostart entry
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/org.kde.logiwheel.autostart.desktop << EOF
[Desktop Entry]
Type=Application
Name=KDE LogiWheel Daemon
Comment=Background service for KDE LogiWheel
Icon=input-mouse
Exec=$BIN_DIR/kde-logiwheel-daemon
Terminal=false
Categories=Qt;KDE;
X-KDE-autostart-condition=true
X-KDE-autostart-phase=2
Hidden=false
NoDisplay=true
EOF

# Install systemd user service
echo -e "${YELLOW}Installing systemd user service...${NC}"
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/kde-logiwheel.service << EOF
[Unit]
Description=KDE LogiWheel - Shortcut Wheel Service
Documentation=https://github.com/Guhan-SenSam/KDE-LogiWheel
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=$BIN_DIR/kde-logiwheel-daemon
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical-session.target
EOF

# Reload systemd
systemctl --user daemon-reload 2>/dev/null || true

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database ~/.local/share/applications 2>/dev/null || true
fi

# Add user to input group (for evdev access on Wayland)
echo ""
echo -e "${YELLOW}For Wayland support, you may need to be in the 'input' group.${NC}"
echo -e "${YELLOW}Run: sudo usermod -aG input \$USER${NC}"
echo -e "${YELLOW}Then log out and back in.${NC}"

# Create default config
echo ""
echo -e "${YELLOW}Creating default configuration...${NC}"
source "$VENV_DIR/bin/activate"
python -c "import sys; sys.path.insert(0, '$INSTALL_DIR'); from src.config import ConfigManager; ConfigManager().load()" 2>/dev/null || true
deactivate

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Installation Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Installation location: $INSTALL_DIR"
echo "Virtual environment: $VENV_DIR"
echo ""
echo "To start KDE-LogiWheel:"
echo "  1. Run the daemon: kde-logiwheel-daemon"
echo "  2. Or enable the service: systemctl --user enable --now kde-logiwheel"
echo ""
echo "To configure:"
echo "  - Run: kde-logiwheel-config"
echo "  - Or find 'KDE LogiWheel' in your application menu"
echo ""
echo "Default trigger: Super+Alt+W (hold to show wheel)"
echo ""
echo "For Logitech mouse integration, see the README for logid setup."
echo ""
