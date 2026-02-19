import click
import sys
from edgeforge.cli.commands import optimize, verify, deploy

@click.group()
@click.version_option(version="0.1.0")
def main():
    """EdgeForge: Military-grade Edge AI optimization and deployment suite."""
    pass

main.add_command(optimize.optimize)
main.add_command(verify.verify)
main.add_command(deploy.deploy)

if __name__ == "__main__":
    main()
