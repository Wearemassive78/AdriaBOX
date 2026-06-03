"""Controller routing system for the AdriaBOX command-line interface."""
import argparse
import getpass
import sys
import jwt

from client.core import AdriaClient
from client.session import SessionManager
from client.config import load_client_config
import client.ui as ui


class AdriaCLI:
    def __init__(self):
        self.parser = argparse.ArgumentParser(description="AdriaBOX CLI Reference Manual", formatter_class=argparse.RawTextHelpFormatter, add_help=False)
        self.subparsers = self.parser.add_subparsers(dest="command", help="Available commands:")
        self.commands_info = {}
        self.admin_commands = {"cluster-status", "users", "userdel"}

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
        self._add_cmd("users", "adria users\nDisplays all registered users and their footprint (Admin).")
        self._add_cmd("userdel", "adria userdel <username>\nDeletes a user and their files (Admin).", ["username"])

        config = load_client_config()
        self.client = AdriaClient(metadata_url=config.metadata_url, request_timeout=config.request_timeout)

    def _add_cmd(self, name, help_text, args_list=None):
        parser = self.subparsers.add_parser(name, help=help_text)
        if args_list:
            for arg in args_list: parser.add_argument(arg)
        self.commands_info[name] = help_text
        return parser

    def run(self):
        if len(sys.argv) == 1 or sys.argv[1] in ("-h", "--help"): 
            return self._show_help()
        args = self.parser.parse_args()

        try:
            if args.command == "register": self._handle_register(args.username, args.password)
            elif args.command == "login": self._handle_login(args.username, args.password)
            elif args.command == "whoami": self._handle_whoami()
            elif args.command == "logout": self._handle_logout()
            elif args.command == "upload": self._handle_upload(args.local_filepath, args.destination)
            elif args.command == "download": self._handle_download(args.filename, args.output)
            elif args.command == "rm": self._handle_rm(args.remote_filepath)
            elif args.command == "mkdir": self._handle_mkdir(args.directory_path)
            elif args.command == "rmdir": self._handle_rmdir(args.directory_path)
            elif args.command == "ls": self._handle_ls(args.directory_path)
            elif args.command == "quota": self._handle_quota()
            elif args.command == "mv": self._handle_mv(args.source, args.destination)
            elif args.command == "cluster-status": self._handle_cluster_status()
            elif args.command == "users": self._handle_users()        
            elif args.command == "userdel": self._handle_userdel(args.username)
            else: self._show_help()
        except Exception as e:
            ui.print_error(str(e))

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
        uname, role = self._get_current_user()
        ui.render_help(uname, role, self.commands_info, self.admin_commands)

    def _is_admin(self):
        _, role = self._get_current_user()
        return role == "admin"

    def _handle_register(self, username, password):
        self.client.register(username, password)
        ui.print_success("Registration successful. Please login.")

    def _handle_login(self, username, password):
        self.client.login(username, password)
        ui.print_success("Login successful. Session active.")

    def _handle_logout(self):
        self.client.logout()
        ui.print_warning("Logged out successfully.")

    def _handle_whoami(self):
        uname, role = self._get_current_user()
        if uname:
            ui.print_success(f"{uname} — role: {role}")
        else:
            ui.print_warning("Not authenticated")

    def _handle_upload(self, local_filepath, destination):
        result = self.client.upload(local_filepath, destination)
        ui.render_upload_complete(result)

    def _handle_download(self, filename, output):
        dest = self.client.download(filename, output)
        ui.print_success(f"Successfully downloaded to: {dest}")

    def _handle_ls(self, directory_path):
        files = self.client.list_files(directory_path)
        ui.render_ls(directory_path, files)

    def _handle_mkdir(self, directory_path):
        self.client.mkdir(directory_path)
        ui.print_success(f"Directory created: {directory_path}")

    def _handle_rmdir(self, directory_path):
        self.client.rmdir(directory_path)
        ui.print_warning(f"Directory removed: {directory_path}")

    def _handle_rm(self, filename):
        self.client.rm(filename)
        ui.print_warning(f"File deleted successfully: {filename}")

    def _handle_mv(self, source, destination):
        result = self.client.mv(source, destination)
        ui.print_success(result.get("message", "Moved successfully."))

    def _handle_quota(self):
        total = self.client.get_quota()
        ui.render_quota(total)

    def _handle_cluster_status(self):
        if not self._is_admin(): raise Exception("Admin privileges required.")
        status = self.client.cluster_status()
        ui.render_cluster_status(status)

    def _handle_users(self):
        if not self._is_admin(): raise Exception("Admin privileges required.")
        users = self.client.admin_list_users()
        ui.render_users(users)

    def _handle_userdel(self, username):
        if not self._is_admin(): raise Exception("Admin privileges required.")
        admin_password = getpass.getpass("Admin password: ")
        result = self.client.admin_delete_user(username, admin_password)
        ui.print_warning(result.get("message", f"User '{username}' deleted."))


def main():
    ui.render_welcome()
    AdriaCLI().run()

if __name__ == "__main__":
    main()

