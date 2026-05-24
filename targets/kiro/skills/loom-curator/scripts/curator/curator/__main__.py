'''CLI entry point. Subcommands wire to runtime functions.'''
import typer

from curator import runtime, status
from curator import source, vault, builders

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)

app.command('ingest')(runtime.cli_ingest)
app.command('next')(runtime.cli_next)
app.command('complete')(runtime.cli_complete)
app.command('status')(status.cli_status)

app.add_typer(source.app, name='source')
app.add_typer(vault.app, name='vault')
app.add_typer(builders.app, name='builders')

if __name__ == '__main__':
    app()
