#!/bin/bash
#
# KDE-LogiWheel Uninstallation Script
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/kde-logiwheel"
BIN_DIR="$HOME/.local/bin"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/kde-logiwheel"

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}  KDE-LogiWheel Uninstallation${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""

# Stop the service if running
echo -e "${YELLOW}Stopping service...${NC}"
systemctl --user stop kde-logiwheel 2>/dev/null || true
systemctl --user disable kde-logiwheel 2>/dev/null || true

# Remove executables
echo -e "${YELLOW}Removing executables...${NC}"
rm -f "$BIN_DIR/kde-logiwheel"
rm -f "$BIN_DIR/kde-logiwheel-daemon"
rm -f "$BIN_DIR/kde-logiwheel-config"

# Remove desktop entries
echo -e "${YELLOW}Removing desktop entries...${NC}"
rm -f ~/.local/share/applications/org.kde.logiwheel.desktop
rm -f ~/.config/autostart/org.kde.logiwheel.autostart.desktop

# Remove systemd service
echo -e "${YELLOW}Removing systemd service...${NC}"
rm -f ~/.config/systemd/user/kde-logiwheel.service
systemctl --user daemon-reload 2>/dev/null || true

# Remove installation directory (includes venv)
echo -e "${YELLOW}Removing installation directory...${NC}"
rm -rf "$INSTALL_DIR"

# Ask about config
echo ""
echo -e "${YELLOW}Remove configuration files at $CONFIG_DIR? [y/N]${NC}"
read -r response
if [[ "$response" =~ ^[Yy]$ ]]; then
    rm -rf "$CONFIG_DIR"
    echo -e "${GREEN}Configuration removed.${NC}"
else
    echo -e "${GREEN}Configuration preserved at $CONFIG_DIR${NC}"
fi

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database ~/.local/share/applications 2>/dev/null || true
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Uninstallation Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
