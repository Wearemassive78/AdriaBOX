"""Terminal UI Rendering engine for AdriaBOX CLI using Rich."""
import sys

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.table import Table
    from rich.columns import Columns
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None


def print_success(message: str):
    """Render a standard success message."""
    if RICH_AVAILABLE:
        console.print(f"[green]{message}[/green]")
    else:
        print(message)


def print_warning(message: str):
    """Render a transient fallback or warning message."""
    if RICH_AVAILABLE:
        console.print(f"[yellow]{message}[/yellow]")
    else:
        print(message)


def print_error(message: str):
    """Render a critical error layout."""
    if RICH_AVAILABLE:
        console.print(f"[bold red]{message}[/bold red]")
    else:
        print(f"Error: {message}")


def render_welcome():
    """Render the application branding banner upon execution."""
    if RICH_AVAILABLE:
        console.print(Markdown("# :anchor: AdriaBOX\nA compact CLI for the AdriaBOX project."))


def render_help(uname: str, role: str, commands_info: dict, admin_commands: set):
    """Dynamically build the context-aware help menu based on user role authorization."""
    if not RICH_AVAILABLE:
        print("AdriaBOX CLI Reference Manual")
        for cmd, help_text in sorted(commands_info.items()):
            if cmd in admin_commands and role != "admin":
                continue
            print(f"{cmd}\n  {help_text}")
        return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Command", style="cyan", no_wrap=True)
    table.add_column("Usage", style="green")
    
    for cmd in sorted(commands_info.keys()):
        if cmd in admin_commands and role != "admin":
            continue
        parts = commands_info[cmd].split("\n", 1)
        if cmd in admin_commands:
            table.add_row(f"[bold red]{cmd}[/bold red]", f"[red]{parts[0]}[/red]")
        else:
            table.add_row(cmd, parts[0])

    user_text = f"[bold cyan]Username:[/bold cyan] {uname}\n[bold green]Role:[/bold green] {role}" if uname else "[yellow]Username:[/yellow] Not authenticated"
    console.print(Columns([Panel("[bold cyan]AdriaBOX CLI[/bold cyan]", width=55), Panel(user_text, title="Current user", width=35)]))
    console.print(Panel("[bold red]Red[/bold red] = admin commands\n[cyan]Cyan[/cyan]/[green]green[/green] = user commands", title="Legend", border_style="dim"))
    console.print(table)


def render_upload_complete(result: dict):
    """Format and render the upload plan completion report."""
    remote_path = result.get('remote_path')
    if not RICH_AVAILABLE:
        print(f"Upload completed: {remote_path}")
        return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Chunk", style="cyan")
    table.add_column("Node", style="green")
    table.add_column("Bytes")
    
    for c in result.get("chunks", []): 
        table.add_row(str(c["index"]), c["node_id"], str(c["size"]))
        
    console.print(f"[green]Upload completed:[/green] {remote_path}")
    console.print(table)


def render_ls(directory_path: str, files: list):
    """Draw the dynamic object storage tree catalog hierarchy."""
    if not RICH_AVAILABLE:
        print(files)
        return

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


def render_quota(total_bytes: int):
    """Render the tenant volume occupancy metrics layout."""
    size_str = f"{total_bytes / (1024**3):.2f} GB" if total_bytes > 1024**3 else f"{total_bytes / (1024**2):.2f} MB" if total_bytes > 1024**2 else f"{total_bytes / 1024:.2f} KB"
    if RICH_AVAILABLE:
        console.print(Panel(f"[bold cyan]Used:[/bold cyan] [green]{size_str}[/green]", title="Quota", width=30))
    else:
        print(size_str)


def render_cluster_status(status: dict):
    """Display the holistic monitoring matrix for infrastructure operational state."""
    metadata = status.get("metadata", {})
    nodes = status.get("nodes", [])

    if not RICH_AVAILABLE:
        print(f"Metadata: {metadata.get('status')} ({metadata.get('url')})")
        for node in nodes:
            print(f"{node.get('node_id')}: {node.get('status')} http={node.get('host')}:{node.get('http_port')} tcp={node.get('host')}:{node.get('tcp_port')}")
        return

    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("Node", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("HTTP", style="dim")
    table.add_column("TCP", style="dim")
    table.add_column("Storage Dir", style="green")

    for node in nodes:
        is_ok = node.get("status") == "ok"
        status_text = "[bold green]online[/bold green]" if is_ok else "[bold red]offline[/bold red]"
        table.add_row(
            str(node.get("node_id")),
            status_text,
            f"{node.get('host')}:{node.get('http_port')}",
            f"{node.get('host')}:{node.get('tcp_port')}",
            str(node.get("storage_dir") or "-")
        )

    metadata_status = metadata.get("status", "unknown")
    metadata_text = f"[bold green]{metadata_status}[/bold green]" if metadata_status == "ok" else f"[bold red]{metadata_status}[/bold red]"
    console.print(Panel(table, title=f"Cluster Status - Metadata {metadata_text} ({metadata.get('url')})", border_style="red"))


def render_users(users: list):
    """Draw the centralized multi-tenant membership footprint overview table."""
    if not RICH_AVAILABLE:
        print(users)
        return

    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("ID", style="dim", justify="center")
    table.add_column("Username", style="cyan")
    table.add_column("Role", style="green")
    table.add_column("Space Used", justify="right")
    table.add_column("Registered At", style="dim")

    for u in users:
        total = u.get("total_used", 0)
        size_str = f"{total / (1024**3):.2f} GB" if total > 1024**3 else f"{total / (1024**2):.2f} MB" if total > 1024**2 else f"{total / 1024:.2f} KB" if total > 0 else "0 Bytes"
        role_style = f"[bold red]{u.get('role')}[/bold red]" if u.get("role") == "admin" else u.get("role")

        table.add_row(str(u.get("id")), u.get("username"), role_style, size_str, u.get("created_at")[:16].replace("T", " "))
    console.print(Panel(table, title="AdriaBOX Cluster Membership Directory", border_style="red"))

