"""
Main entry point for KDE-LogiWheel.
"""

import sys
import argparse


def main():
    parser = argparse.ArgumentParser(
        description="KDE-LogiWheel - A Logitech-style shortcut wheel for KDE"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Daemon command
    daemon_parser = subparsers.add_parser("daemon", help="Run the background daemon")
    daemon_parser.add_argument(
        "--config", "-c",
        help="Path to config file",
        default=None
    )

    # Config UI command
    config_parser = subparsers.add_parser("config", help="Open configuration UI")

    # Show wheel command (via D-Bus)
    show_parser = subparsers.add_parser("show", help="Show the wheel (requires daemon)")

    # Hide wheel command
    hide_parser = subparsers.add_parser("hide", help="Hide the wheel")

    # Toggle wheel command
    toggle_parser = subparsers.add_parser("toggle", help="Toggle the wheel")

    # Generate logid config
    logid_parser = subparsers.add_parser(
        "logid-config",
        help="Generate logid configuration"
    )
    logid_parser.add_argument(
        "--device", "-d",
        help="Device name",
        required=True
    )
    logid_parser.add_argument(
        "--button", "-b",
        help="Button CID (hex, e.g., 0xc3)",
        required=True
    )

    args = parser.parse_args()

    if args.command == "daemon" or args.command is None:
        from .service.daemon import main as daemon_main
        daemon_main()

    elif args.command == "config":
        from .ui.main_window import main as config_main
        config_main()

    elif args.command == "show":
        _dbus_command("ShowWheel")

    elif args.command == "hide":
        _dbus_command("HideWheel")

    elif args.command == "toggle":
        _dbus_command("ToggleWheel")

    elif args.command == "logid-config":
        from .logid import LogidHelper
        helper = LogidHelper()
        button_cid = int(args.button, 16) if args.button.startswith("0x") else int(args.button)
        config = helper.generate_wheel_trigger_config(args.device, button_cid)
        print(config)

    else:
        parser.print_help()


def _dbus_command(method: str):
    """Execute a D-Bus command."""
    try:
        import dbus
        bus = dbus.SessionBus()
        obj = bus.get_object("org.kde.LogiWheel", "/org/kde/LogiWheel")
        interface = dbus.Interface(obj, "org.kde.LogiWheel")
        getattr(interface, method)()
    except Exception as e:
        print(f"Error: Could not connect to daemon. Is it running?")
        print(f"Details: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
