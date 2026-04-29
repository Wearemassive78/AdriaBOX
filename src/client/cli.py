import argparse
import sys
import os
from client.core import AdriaClient  # Importing the engine we just built

# Optional rich for colored output / banners. Falls back to plain text if unavailable.
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.table import Table

    RICH_AVAILABLE = True
    console = Console()
except Exception:
    RICH_AVAILABLE = False
    console = None


class AdriaCLI:
    """Command Line Interface for AdriaBOX."""

    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description="AdriaBOX CLI Reference Manual",
            formatter_class=argparse.RawTextHelpFormatter  # Permette una formattazione più pulita
        )
        self.subparsers = self.parser.add_subparsers(dest="command", help="Available commands:")
        # Keep command metadata for a nicer help table
        self.commands_info = {}

        # --- Authentication ---
        reg_help = "adria register <username> <password>\nCreates a new user account."
        register_parser = self.subparsers.add_parser("register", help=reg_help)
        register_parser.add_argument("username", type=str)
        register_parser.add_argument("password", type=str)
        self.commands_info["register"] = reg_help

        login_help = "adria login <username> <password>\nAuthenticates and retrieves a session token."
        login_parser = self.subparsers.add_parser("login", help=login_help)
        login_parser.add_argument("username", type=str)
        login_parser.add_argument("password", type=str)
        self.commands_info["login"] = login_help

        logout_help = "adria logout\nInvalidates session and clears credentials."
        self.subparsers.add_parser("logout", help=logout_help)
        self.commands_info["logout"] = logout_help

        # --- File Operations (Stubs for help menu) ---
        upload_help = "adria upload <local_filepath> [-d <remote_dir>]\nUploads a file to the cluster."
        upload_parser = self.subparsers.add_parser("upload", help=upload_help)
        upload_parser.add_argument("local_filepath")
        upload_parser.add_argument("-d", "--destination", default="/", help="Remote destination folder")
        self.commands_info["upload"] = upload_help

        download_help = "adria download <remote_filepath> [-o <local_output_path>]\nRetrieves a file."
        download_parser = self.subparsers.add_parser("download", help=download_help)
        download_parser.add_argument("remote_filepath")
        download_parser.add_argument("-o", "--output", help="Local save path")
        self.commands_info["download"] = download_help

        rm_help = "adria rm <remote_filepath>\nPermanently deletes a file."
        rm_parser = self.subparsers.add_parser("rm", help=rm_help)
        rm_parser.add_argument("remote_filepath")
        self.commands_info["rm"] = rm_help

        mv_help = "adria mv <source> <destination>\nMoves or renames a file."
        mv_parser = self.subparsers.add_parser("mv", help=mv_help)
        mv_parser.add_argument("source")
        mv_parser.add_argument("destination")
        self.commands_info["mv"] = mv_help

        # --- Directory Operations (Stubs for help menu) ---
        mkdir_help = "adria mkdir <directory_path>\nCreates a new remote directory."
        mkdir_parser = self.subparsers.add_parser("mkdir", help=mkdir_help)
        mkdir_parser.add_argument("directory_path")
        self.commands_info["mkdir"] = mkdir_help

        rmdir_help = "adria rmdir <directory_path>\nRemoves a remote directory."
        rmdir_parser = self.subparsers.add_parser("rmdir", help=rmdir_help)
        rmdir_parser.add_argument("directory_path")
        self.commands_info["rmdir"] = rmdir_help

        ls_help = "adria ls [-l] [<directory_path>]\nLists directory contents."
        ls_parser = self.subparsers.add_parser("ls", help=ls_help)
        ls_parser.add_argument("-l", action="store_true", help="Detailed output")
        ls_parser.add_argument("directory_path", nargs="?", default="/")
        self.commands_info["ls"] = ls_help

        # --- System Operations (Stubs for help menu) ---
        quota_help = "adria quota\nDisplays storage usage and limits."
        self.subparsers.add_parser("quota", help=quota_help)
        self.commands_info["quota"] = quota_help

        status_help = "adria cluster-status [--global] [-u <username>]\nDisplays cluster health (Admin)."
        status_parser = self.subparsers.add_parser("cluster-status", help=status_help)
        status_parser.add_argument("--global", action="store_true", help="Global cluster health")
        status_parser.add_argument("-u", "--user", help="Query specific user quota")
        self.commands_info["cluster-status"] = status_help

        self.client = AdriaClient(metadata_url="http://127.0.0.1:5000")

    def run(self):
        """
        Parses the arguments and executes the requested operation.
        """
        # Automatically parses sys.argv and creates an object with our variables
        args = self.parser.parse_args()

        if args.command == "register":
            self._handle_register(args.username, args.password)
        elif args.command == "login":
            self._handle_login(args.username, args.password)
        elif args.command == "logout":
            self._handle_logout()
        else:
            # If no command is given, print a nicer help table when possible
            if RICH_AVAILABLE and console:
                self._print_fancy_help()
            else:
                self.parser.print_help()

    def _print_fancy_help(self):
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Command", style="cyan", no_wrap=True)
        table.add_column("Usage", style="green")
        table.add_column("Description", style="white")

        for cmd in sorted(self.commands_info.keys()):
            text = self.commands_info[cmd]
            parts = text.split("\n", 1)
            usage = parts[0]
            desc = parts[1] if len(parts) > 1 else ""
            table.add_row(cmd, usage, desc)

        console.print(Panel("[bold cyan]AdriaBOX CLI[/bold cyan]\nUse one of the commands below:", expand=False))
        console.print(table)

    def _handle_register(self, username, password):
        try:
            # We call the logic layer (AdriaClient)
            self.client.register(username, password)
            if RICH_AVAILABLE and console:
                console.print("[green]Registration successful.[/green] Please login.")
            else:
                print("Registration successful. Please login.")
        except Exception as e:
            print(f"Error during registration: {e}")

    def _handle_login(self, username, password):
        try:
            self.client.login(username, password)
            if RICH_AVAILABLE and console:
                console.print("[green]Login successful.[/green] Session active.")
            else:
                print("Login successful. Session active.")
        except Exception as e:
            print(f"Error during login: {e}")

    def _handle_logout(self):
        try:
            self.client.logout()
            if RICH_AVAILABLE and console:
                console.print("[yellow]Logged out successfully.[/yellow] Local session cleared.")
            else:
                print("Logged out successfully. Local session cleared.")
        except Exception as e:
            print(f"Error during logout: {e}")


def main():
    """Entry point for the console script."""
    # Print a friendly banner when running as entrypoint
    if RICH_AVAILABLE and console:
        console.print(Markdown("# :anchor: AdriaBOX\nA compact CLI for the AdriaBOX project."))

    cli = AdriaCLI()
    cli.run()


# It runs only if this script is executed directly from the terminal.
if __name__ == "__main__":
    main()
