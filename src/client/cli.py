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
    def __init__(self):
        self.parser = argparse.ArgumentParser(description="AdriaBOX CLI Reference Manual", formatter_class=argparse.RawTextHelpFormatter, add_help=False)
        self.subparsers = self.parser.add_subparsers(dest="command", help="Available commands:")
        self.commands_info = {}

        self._add_cmd("register", "adria register <username> <password>\nCreates a new user account.", ["username", "password"])
        self._add_cmd("login", "adria login <username> <password>\nAuthenticates and retrieves a session token.", ["username", "password"])
        self._add_cmd("whoami", "adria whoami\nShow current authenticated user and role.")
        self._add_cmd("logout", "adria logout\nInvalidates session and clears credentials.")
        
        up_parser = self._add_cmd("upload", "adria upload <local_filepath> [-d <remote_dir>]\nUploads a file to the cluster.", ["local_filepath"])
        up_parser.add_argument("-d", "--destination", default="/", help="Remote destination folder")
        
        dl_parser = self._add_cmd("download", "adria download <remote_filepath> [-o <local_dest>]\nRetrieves a file.", ["filename"])
        dl_parser.add_argument("-o", "--output", help="Local save path")
        
        self._add_cmd("rm", "adria rm <remote_filepath>\nPermanently deletes a file.", ["remote_filepath"])
        self._add_cmd("mkdir", "adria mkdir <directory_path>\nCreates a new remote directory.", ["directory_path"])
        self._add_cmd("rmdir", "adria rmdir <directory_path>\nRemoves a remote directory and its contents.", ["directory_path"])
        self._add_cmd("mv", "adria mv <source> <destination>\nMoves or renames a file.", ["source", "destination"])
        
        ls_parser = self._add_cmd("ls", "adria ls [<directory_path>]\nLists directory contents.")
        ls_parser.add_argument("directory_path", nargs="?", default="/")
        
        self._add_cmd("quota", "adria quota\nDisplays storage usage.")
        self._add_cmd("cluster-status", "adria cluster-status\nDisplays cluster health (Admin).")

        config = load_client_config()
        self.client = AdriaClient(metadata_url=config.metadata_url, request_timeout=config.request_timeout)

    def _add_cmd(self, name, help_text, args_list=None):
        parser = self.subparsers.add_parser(name, help=help_text)
        if args_list:
            for arg in args_list: parser.add_argument(arg)
        self.commands_info[name] = help_text
        return parser

    def run(self):
        if len(sys.argv) == 1 or sys.argv[1] in ("-h", "--help"): return self._show_help()
        args = self.parser.parse_args()

        if args.command == "register": self._handle_register(args.username, args.password)
        elif args.command == "login": self._handle_login(args.username, args.password)
        elif args.command == "whoami": self._handle_whoami()
        elif args.command == "logout": self._handle_logout()
        elif args.command == "upload": self._handle_upload(args.local_filepath, args.destination)
        elif args.command == "download":
            try:
                dest = self.client.download(args.filename, args.output)
                (console.print(f"[green]Successfully downloaded to:[/green] {dest}") if RICH_AVAILABLE else print(f"Successfully downloaded to: {dest}"))
            except Exception as e: print(f"Error during download: {e}")
        elif args.command == "rm": self._handle_rm(args.remote_filepath)
        elif args.command == "mkdir": self._handle_mkdir(args.directory_path)
        elif args.command == "rmdir": self._handle_rmdir(args.directory_path)
        elif args.command == "ls": self._handle_ls(args.directory_path)
        elif args.command == "quota": self._handle_quota()
        elif args.command == "mv": self._handle_mv(args.source, args.destination)
        else: self._show_help()

    def _get_current_user(self):
        sm = SessionManager()
        data = sm.load_session() or {}
        if "token" in data:
            try:
                payload = jwt.decode(data["token"], options={"verify_signature": False})
                return payload.get("username"), payload.get("role", "user")
            except Exception: pass
        return None, None

    def _show_help(self):
        if not RICH_AVAILABLE: return self.parser.print_help()
        uname, role = self._get_current_user()
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Command", style="cyan", no_wrap=True)
        table.add_column("Usage", style="green")
        
        for cmd in sorted(self.commands_info.keys()):
            parts = self.commands_info[cmd].split("\n", 1)
            table.add_row(cmd, parts[0])

        user_text = f"[bold cyan]Username:[/bold cyan] {uname}\n[bold green]Role:[/bold green] {role}" if uname else "[yellow]Username:[/yellow] Not authenticated"
        console.print(Columns([Panel("[bold cyan]AdriaBOX CLI[/bold cyan]", width=55), Panel(user_text, title="Current user", width=35)]))
        console.print(table)

    def _handle_register(self, username, password):
        try:
            self.client.register(username, password)
            (console.print("[green]Registration successful.[/green] Please login.") if RICH_AVAILABLE else print("Registration successful. Please login."))
        except Exception as e: print(f"Error: {e}")

    def _handle_login(self, username, password):
        try:
            self.client.login(username, password)
            (console.print("[green]Login successful.[/green] Session active.") if RICH_AVAILABLE else print("Login successful."))
        except Exception as e: print(f"Error: {e}")

    def _handle_logout(self):
        try:
            self.client.logout()
            (console.print("[yellow]Logged out successfully.[/yellow]") if RICH_AVAILABLE else print("Logged out."))
        except Exception as e: print(f"Error: {e}")

    def _handle_whoami(self):
        uname, role = self._get_current_user()
        msg = f"[bold]{uname}[/bold] — [green]{role}[/green]" if uname else "[yellow]Not authenticated[/yellow]"
        (console.print(msg) if RICH_AVAILABLE else print(msg.replace('[bold]', '').replace('[/bold]', '')))

    def _handle_upload(self, local_filepath, destination):
        try:
            result = self.client.upload(local_filepath, destination)
            if RICH_AVAILABLE:
                table = Table(show_header=True, header_style="bold magenta")
                table.add_column("Chunk", style="cyan"); table.add_column("Node", style="green"); table.add_column("Bytes")
                for c in result.get("chunks", []): table.add_row(str(c["index"]), c["node_id"], str(c["size"]))
                console.print(f"[green]Upload completed:[/green] {result.get('remote_path')}"); console.print(table)
            else: print(f"Upload completed: {result.get('remote_path')}")
        except Exception as e: print(f"Error during upload: {e}")

    def _handle_ls(self, directory_path):
        try:
            files = self.client.list_files(directory_path)
            if RICH_AVAILABLE:
                table = Table(show_header=True, header_style="bold magenta", box=None)
                table.add_column("Name", style="cyan")
                table.add_column("Type", style="blue")
                table.add_column("Size", justify="right")
                table.add_column("Chunks", style="dim", justify="center")

                for f in files:
                    is_dir, name = f.get("is_dir", False), f.get("filename")
                    if is_dir:
                        table.add_row(f"[bold blue]🗀  {name}[/bold blue]", "[bold blue]DIR[/bold blue]", "-", "-")
                    else:
                        size_val = f.get('size', 0)
                        readable_size = f"{size_val / (1024**3):.2f} GB" if size_val > 1024**3 else f"{size_val / (1024**2):.2f} MB" if size_val > 1024**2 else f"{size_val / 1024:.2f} KB"
                        table.add_row(f"📄 {name}", "FILE", readable_size, str(f.get("chunks")))
                
                console.print(Panel(table, title=f"Remote Filesystem: {directory_path}", border_style="blue"))
            else: print(files)
        except Exception as e: print(f"Error: {e}")

    def _handle_mkdir(self, directory_path):
        try:
            self.client.mkdir(directory_path)
            (console.print(f"[green]Directory created:[/green] {directory_path}") if RICH_AVAILABLE else print("Created."))
        except Exception as e: print(f"Error: {e}")

    def _handle_rmdir(self, directory_path):
        try:
            self.client.rmdir(directory_path)
            (console.print(f"[yellow]Directory removed:[/yellow] {directory_path}") if RICH_AVAILABLE else print("Removed."))
        except Exception as e: print(f"Error: {e}")

    def _handle_rm(self, filename):
        try:
            self.client.rm(filename)
            (console.print(f"[yellow]File deleted successfully:[/yellow] {filename}") if RICH_AVAILABLE else print("Deleted."))
        except Exception as e: print(f"Error: {e}")

    def _handle_mv(self, source, destination):
        try:
            result = self.client.mv(source, destination)
            msg = result.get("message", "Moved successfully.")
            if RICH_AVAILABLE and console:
                console.print(f"[green]{msg}[/green]")
            else:
                print(msg)
        except Exception as e:
            print(f"Error: {e}")

    def _handle_quota(self):
        try:
            total = self.client.get_quota()
            size_str = f"{total / (1024**3):.2f} GB" if total > 1024**3 else f"{total / (1024**2):.2f} MB" if total > 1024**2 else f"{total / 1024:.2f} KB"
            if RICH_AVAILABLE: console.print(Panel(f"[bold cyan]Used:[/bold cyan] [green]{size_str}[/green]", title="Quota", width=30))
            else: print(size_str)
        except Exception as e: print(f"Error: {e}")

def main():
    if RICH_AVAILABLE and console: console.print(Markdown("# :anchor: AdriaBOX\nA compact CLI for the AdriaBOX project."))
    AdriaCLI().run()

if __name__ == "__main__": main()

