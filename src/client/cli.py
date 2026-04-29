import argparse
import sys
from client.core import AdriaClient  # Importing the engine we just built

class AdriaCLI:
    """Command Line Interface for AdriaBOX."""

    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description="AdriaBOX CLI Reference Manual",
            formatter_class=argparse.RawTextHelpFormatter # Permette una formattazione più pulita
        )
        self.subparsers = self.parser.add_subparsers(dest="command", help="Available commands:")

        # --- Authentication ---
        register_parser = self.subparsers.add_parser("register", help="adria register <username> <password>\nCreates a new user account.")
        register_parser.add_argument("username", type=str)
        register_parser.add_argument("password", type=str)

        login_parser = self.subparsers.add_parser("login", help="adria login <username> <password>\nAuthenticates and retrieves a session token.")
        login_parser.add_argument("username", type=str)
        login_parser.add_argument("password", type=str)

        self.subparsers.add_parser("logout", help="adria logout\nInvalidates session and clears credentials.")

        # --- File Operations (Stubs for help menu) ---
        upload_parser = self.subparsers.add_parser("upload", help="adria upload <local_filepath> [-d <remote_dir>]\nUploads a file to the cluster.")
        upload_parser.add_argument("local_filepath")
        upload_parser.add_argument("-d", "--destination", default="/", help="Remote destination folder")

        download_parser = self.subparsers.add_parser("download", help="adria download <remote_filepath> [-o <local_output_path>]\nRetrieves a file.")
        download_parser.add_argument("remote_filepath")
        download_parser.add_argument("-o", "--output", help="Local save path")

        rm_parser = self.subparsers.add_parser("rm", help="adria rm <remote_filepath>\nPermanently deletes a file.")
        rm_parser.add_argument("remote_filepath")

        mv_parser = self.subparsers.add_parser("mv", help="adria mv <source> <destination>\nMoves or renames a file.")
        mv_parser.add_argument("source")
        mv_parser.add_argument("destination")

        # --- Directory Operations (Stubs for help menu) ---
        mkdir_parser = self.subparsers.add_parser("mkdir", help="adria mkdir <directory_path>\nCreates a new remote directory.")
        mkdir_parser.add_argument("directory_path")

        rmdir_parser = self.subparsers.add_parser("rmdir", help="adria rmdir <directory_path>\nRemoves a remote directory.")
        rmdir_parser.add_argument("directory_path")

        ls_parser = self.subparsers.add_parser("ls", help="adria ls [-l] [<directory_path>]\nLists directory contents.")
        ls_parser.add_argument("-l", action="store_true", help="Detailed output")
        ls_parser.add_argument("directory_path", nargs='?', default="/")

        # --- System Operations (Stubs for help menu) ---
        self.subparsers.add_parser("quota", help="adria quota\nDisplays storage usage and limits.")
        
        status_parser = self.subparsers.add_parser("cluster-status", help="adria cluster-status [--global] [-u <username>]\nDisplays cluster health (Admin).")
        status_parser.add_argument("--global", action="store_true", help="Global cluster health")
        status_parser.add_argument("-u", "--user", help="Query specific user quota")

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
            # If no command is given, print the help menu
            self.parser.print_help()

    # The underscore prefix (e.g., _handle_register) is a Python convention.
    # It means "this method is private, only meant to be used inside this class".
    # It's similar to the 'static' keyword for functions in a C file.
    def _handle_register(self, username, password):
        try:
            # We call the logic layer (AdriaClient)
            self.client.register(username, password)
            print("Registration successful. Please login.")
        except Exception as e:
            print(f"Error during registration: {e}")

    def _handle_login(self, username, password):
        try:
            self.client.login(username, password)
            print("Login successful. Session active.")
        except Exception as e:
            print(f"Error during login: {e}")

    def _handle_logout(self):
        try:
            self.client.logout()
            print("Logged out successfully. Local session cleared.")
        except Exception as e:
            print(f"Error during logout: {e}")

def main():
    """Entry point for the console script."""
    cli = AdriaCLI()
    cli.run()


# It runs only if this script is executed directly from the terminal.
if __name__ == "__main__":
    main()
