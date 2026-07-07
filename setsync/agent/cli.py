import click
import os
import sys
from pathlib import Path
from agent.config import CORE_SERVICE_URL, PC_ID
from agent.db import init_agent_db
from agent.scanner import scan_directory
from agent.uploader import upload_inventory_data

# Ensure we can load sibling packages
sys.path.append(str(Path(__file__).parent.parent))

@click.group()
def cli():
    """SetSync Inventory Agent CLI."""
    pass

@cli.command()
@click.option("--root", "-r", type=click.Path(exists=True), help="Directory root path to scan")
@click.option("--pc", "-p", type=click.Choice(["A", "B"]), help="PC Identifier (A or B)")
def scan(root, pc):
    """Scan root directory and upload inventory state to Core Service."""
    init_agent_db()
    
    # Resolve root path: default to config or CLI param
    # For simulation, default to setting directories based on pc
    if not pc:
        pc = PC_ID
        
    if not root:
        # Fallback to defaults
        # We can look up from env / defaults
        # For simplicity, if we run locally we can read from env or use defaults
        click.echo(f"No scan root specified. Using default simulator folder for PC-{pc}.")
        # Try importing backend config or fallback
        try:
            from app.config import settings
            root = settings.PC_A_ROOT if pc == "A" else settings.PC_B_ROOT
        except ImportError:
            root = "./test_pc_a" if pc == "A" else "./test_pc_b"
            
    click.echo(f"Scanning directory: {os.path.abspath(root)} for PC-{pc}...")
    
    try:
        files = scan_directory(root)
        click.echo(f"Scan complete. Found {len(files)} files.")
        
        click.echo(f"Uploading inventory to Core Service ({CORE_SERVICE_URL})...")
        res = upload_inventory_data(files, pc)
        
        click.echo(click.style(
            f"Success! Core Service Response: {res.get('message')} (Ingested {res.get('records_ingested')} files).",
            fg="green"
        ))
    except Exception as e:
        click.echo(click.style(f"Failed: {e}", fg="red"), err=True)

@cli.command()
@click.option("--root", "-r", type=click.Path(exists=True), help="Directory root path to watch")
@click.option("--pc", "-p", type=click.Choice(["A", "B"]), help="PC Identifier (A or B)")
def watch(root, pc):
    """Start real-time directory event watcher to sync changes automatically."""
    from agent.watcher import start_watching
    init_agent_db()
    
    if not pc:
        pc = PC_ID
        
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

if __name__ == "__main__":
    cli()
