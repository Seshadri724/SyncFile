import click
import os
import sys
import socket
import requests
from pathlib import Path

# Ensure we can load sibling packages
sys.path.append(str(Path(__file__).parent.parent))

from agent.config import get_agent_config
from agent.db import init_agent_db, set_config
from agent.scanner import scan_directory
from agent.uploader import upload_inventory_data

@click.group()
def cli():
    """SetSync Inventory Agent CLI."""
    pass

@cli.command()
@click.option("--url", "-u", default="http://localhost:8000", help="Core Service URL")
@click.option("--token", "-t", default="setsync_secret_token_123", help="Master API Token for registration")
@click.option("--name", "-n", help="Display name of this device source (default: OS hostname)")
@click.option("--roots", "-d", help="Comma-separated root directory paths to scan")
def init(url, token, name, roots):
    """Interactively register this device as a dynamic source on the Core Service."""
    init_agent_db()
    
    click.echo("=== SetSync Agent Initialization ===")
    
    # Prompt if inputs not provided as options
    if not url:
        url = click.prompt("Enter Core Service URL", default="http://localhost:8000")
    if not token:
        token = click.prompt("Enter master API Token", default="setsync_secret_token_123")
    if not name:
        default_name = socket.gethostname()
        name = click.prompt("Enter device display name", default=default_name)
    if not roots:
        roots = click.prompt("Enter comma-separated root directories to scan (e.g. C:/data or ./test_pc_a)")
        
    roots_list = [r.strip() for r in roots.split(",") if r.strip()]
    
    # Call register API on core service using master token
    register_url = f"{url.rstrip('/')}/sources/register"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "name": name,
        "kind": "device",
        "roots": roots_list
    }
    
    click.echo(f"Registering with Core Service at {register_url}...")
    try:
        res = requests.post(register_url, json=payload, headers=headers, timeout=30)
        res.raise_for_status()
        data = res.json()
        
        source_id = data["source"]["id"]
        agent_key = data["agent_key"]
        
        # Persist config in local agent DB
        set_config("core_url", url)
        set_config("source_id", source_id)
        set_config("agent_key", agent_key)
        set_config("roots", roots)
        
        click.echo(click.style(
            f"Successfully registered! Device registered with ID: {source_id}.",
            fg="green"
        ))
    except Exception as e:
        click.echo(click.style(f"Registration failed: {e}", fg="red"), err=True)
        sys.exit(1)

@cli.command()
@click.option("--root", "-r", help="Directory root path to scan")
@click.option("--pc", "-p", type=click.Choice(["A", "B"]), help="Legacy PC Identifier simulation (A or B)")
def scan(root, pc):
    """Scan root directory and upload inventory state to Core Service."""
    init_agent_db()
    
    core_url = get_agent_config("core_url", "http://localhost:8000")
    
    if pc:
        # Legacy simulation mode
        if not root:
            try:
                from app.config import settings
                root = settings.PC_A_ROOT if pc == "A" else settings.PC_B_ROOT
            except ImportError:
                root = "./test_pc_a" if pc == "A" else "./test_pc_b"
        
        click.echo(f"[Legacy Sim Mode] Scanning directory: {os.path.abspath(root)} for PC-{pc}...")
        try:
            files = scan_directory(root)
            click.echo(f"Scan complete. Found {len(files)} files.")
            res = upload_inventory_data(files, pc)
            click.echo(click.style(
                f"Success! Core Service Response: {res.get('message')} (Ingested {res.get('records_ingested')} files).",
                fg="green"
            ))
        except Exception as e:
            click.echo(click.style(f"Failed: {e}", fg="red"), err=True)
    else:
        # Dynamic dynamic source mode
        source_id = get_agent_config("source_id")
        if not source_id:
            click.echo(click.style("Agent not initialized. Run 'setsync-agent init' first or use legacy --pc simulation option.", fg="yellow"))
            return
            
        if not root:
            roots_str = get_agent_config("roots")
            roots = [r.strip() for r in roots_str.split(",") if r.strip()]
            root = roots[0] if roots else None
            if not root:
                click.echo(click.style("No roots configured. Set them during init or specify --root.", fg="red"))
                return
                
        click.echo(f"Scanning directory: {os.path.abspath(root)} for source: {source_id}...")
        try:
            files = scan_directory(root)
            click.echo(f"Scan complete. Found {len(files)} files.")
            res = upload_inventory_data(files, source_id)
            click.echo(click.style(
                f"Success! Core Service Response: {res.get('message')} (Ingested {res.get('records_ingested')} files).",
                fg="green"
            ))
        except Exception as e:
            click.echo(click.style(f"Failed: {e}", fg="red"), err=True)

@cli.command()
@click.option("--root", "-r", help="Directory root path to watch")
@click.option("--pc", "-p", type=click.Choice(["A", "B"]), help="Legacy PC Identifier simulation (A or B)")
def watch(root, pc):
    """Start real-time directory event watcher to sync changes automatically."""
    from agent.watcher import start_watching
    init_agent_db()
    
    if pc:
        # Legacy simulation mode
        if not root:
            try:
                from app.config import settings
                root = settings.PC_A_ROOT if pc == "A" else settings.PC_B_ROOT
            except ImportError:
                root = "./test_pc_a" if pc == "A" else "./test_pc_b"
        try:
            start_watching(root, pc)
        except Exception as e:
            click.echo(click.style(f"Failed: {e}", fg="red"), err=True)
    else:
        # Dynamic source mode
        source_id = get_agent_config("source_id")
        if not source_id:
            click.echo(click.style("Agent not initialized. Run 'setsync-agent init' first or use legacy --pc simulation option.", fg="yellow"))
            return
            
        if not root:
            roots_str = get_agent_config("roots")
            roots = [r.strip() for r in roots_str.split(",") if r.strip()]
            root = roots[0] if roots else None
            if not root:
                click.echo(click.style("No roots configured. Set them during init or specify --root.", fg="red"))
                return
                
        try:
            start_watching(root, source_id)
        except Exception as e:
            click.echo(click.style(f"Failed: {e}", fg="red"), err=True)

@cli.command()
def run():
    """Start the background Job Executor Loop to listen for delta sync transfers."""
    init_agent_db()
    from agent.job_runner import run_job_loop
    run_job_loop()

if __name__ == "__main__":
    cli()
