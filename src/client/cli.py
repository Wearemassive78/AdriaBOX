import argparse
import sys
import jwt

from client.core import AdriaClient
from client.session import SessionManager
from client.config import load_client_config

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.table import Table
    from rich.columns import Columns

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
            formatter_class=argparse.RawTextHelpFormatter,
            add_help=False,
        )

        self.subparsers = self.parser.add_subparsers(
            dest="command",
            help="Available commands:"
        )

        self.commands_info = {}

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

        whoami_help = "adria whoami\nShow current authenticated user and role."
        self.subparsers.add_parser("whoami", help=whoami_help)
        self.commands_info["whoami"] = whoami_help

        logout_help = "adria logout\nInvalidates session and clears credentials."
        self.subparsers.add_parser("logout", help=logout_help)
        self.commands_info["logout"] = logout_help

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

        quota_help = "adria quota\nDisplays storage usage and limits."
        self.subparsers.add_parser("quota", help=quota_help)
        self.commands_info["quota"] = quota_help

        status_help = "adria cluster-status [--global] [-u <username>]\nDisplays cluster health (Admin)."
        status_parser = self.subparsers.add_parser("cluster-status", help=status_help)
        status_parser.add_argument("--global", action="store_true", help="Global cluster health")
        status_parser.add_argument("-u", "--user", help="Query specific user quota")
        self.commands_info["cluster-status"] = status_help

        config = load_client_config()
        self.client = AdriaClient(
            metadata_url=config.metadata_url,
            request_timeout=config.request_timeout,
        )

    def run(self):
        if len(sys.argv) == 1 or sys.argv[1] in ("-h", "--help"):
            self._show_help()
            return

        args = self.parser.parse_args()

        if args.command == "register":
            self._handle_register(args.username, args.password)
        elif args.command == "login":
            self._handle_login(args.username, args.password)
        elif args.command == "whoami":
            self._handle_whoami()
        elif args.command == "logout":
            self._handle_logout()
        elif args.command == "upload":
            print("Upload command not implemented yet.")
        elif args.command == "download":
            print("Download command not implemented yet.")
        elif args.command == "rm":
            print("Remove command not implemented yet.")
        elif args.command == "mv":
            print("Move command not implemented yet.")
        elif args.command == "mkdir":
            print("Mkdir command not implemented yet.")
        elif args.command == "rmdir":
            print("Rmdir command not implemented yet.")
        elif args.command == "ls":
            print("List command not implemented yet.")
        elif args.command == "quota":
            print("Quota command not implemented yet.")
        elif args.command == "cluster-status":
            print("Cluster status command not implemented yet.")
        else:
            self._show_help()

    def _show_help(self):
        if RICH_AVAILABLE and console:
            self._print_fancy_help()
        else:
            self.parser.print_help()

    def _get_current_user(self):
        uname = getattr(self.client, "current_username", None)
        role = getattr(self.client, "current_role", None)

        if uname:
            return uname, role or "user"

        try:
            sm = SessionManager()
            data = sm.load_session() or {}
            token = data.get("token")

            if token:
                payload = jwt.decode(
                    token,
                    options={"verify_signature": False}
                )

                uname = payload.get("username")
                role = payload.get("role")

                if uname:
                    return uname, role or "user"

        except Exception:
            pass

        return None, None

    def _print_fancy_help(self):
        uname, role = self._get_current_user()

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

        if uname:
            user_text = (
                f"[bold cyan]Username:[/bold cyan] {uname}\n"
                f"[bold green]Role:[/bold green] {role}"
            )
        else:
            user_text = (
                "[yellow]Username:[/yellow] Not authenticated\n"
                "[dim]Role: -[/dim]"
            )

        left_panel = Panel(
            "[bold cyan]AdriaBOX CLI[/bold cyan]\nUse one of the commands below:",
            title="Menu",
            width=55
        )

        right_panel = Panel(
            user_text,
            title="Current user",
            width=35
        )

        console.print()
        console.print(Columns([left_panel, right_panel], equal=False, expand=False))
        console.print()
        console.print(table)

    def _handle_register(self, username, password):
        try:
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

    def _handle_whoami(self):
        try:
            uname, role = self._get_current_user()

            if uname:
                if RICH_AVAILABLE and console:
                    console.print(f"[bold]{uname}[/bold] — [green]{role}[/green]")
                else:
                    print(f"{uname} — {role}")
            else:
                if RICH_AVAILABLE and console:
                    console.print("[yellow]Not authenticated[/yellow]")
                else:
                    print("Not authenticated")

        except Exception as e:
            print(f"Error: {e}")


def main():
    if RICH_AVAILABLE and console:
        console.print(Markdown("# :anchor: AdriaBOX\nA compact CLI for the AdriaBOX project."))

    cli = AdriaCLI()
    cli.run()


if __name__ == "__main__":
    main()
