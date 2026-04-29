import argparse
import sys
from client import AdriaClient  # Importing the engine we just built

class AdriaCLI:
    """Command Line Interface for AdriaBOX."""

    def __init__(self):
        """
        Sets up the command line parser.
        This replaces manual argv parsing or getopt in C.
        """
        self.parser = argparse.ArgumentParser(description="AdriaBOX CLI Reference")
        
        # Subparsers allow us to create commands like 'adria <command> <args>'
        self.subparsers = self.parser.add_subparsers(dest="command", help="Available commands")

        # 1. Command: adria register <username> <password>
        register_parser = self.subparsers.add_parser("register", help="Register a new account")
        register_parser.add_argument("username", type=str)
        register_parser.add_argument("password", type=str)

        # 2. Command: adria login <username> <password>
        login_parser = self.subparsers.add_parser("login", help="Login to AdriaBOX")
        login_parser.add_argument("username", type=str)
        login_parser.add_argument("password", type=str)

        # Instantiate the client (Hardcoding localhost for now, we can make this dynamic later)
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

# This is the exact Python equivalent of 'int main()'. 
# It runs only if this script is executed directly from the terminal.
if __name__ == "__main__":
    cli = AdriaCLI()
    cli.run()
