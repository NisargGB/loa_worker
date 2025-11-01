"""
CLI entry point for LoA Worker.
"""
import asyncio

import click
from rich.console import Console
from rich.table import Table

from channels.dummy_channel import DummyChannel
from core.enums import CaseStatus, CaseType
from llm.service import get_llm_service
from pipeline.orchestrator import PipelineOrchestrator
from pipeline.pre_filter import PreFilter
from storage.audit_repository import AuditRepository
from storage.case_repository import CaseRepository
from storage.firestore_client import FirestoreClient

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """LoA Worker - Intelligent agent for processing Letters of Authority."""
    pass


@cli.command()
@click.option(
    "--source",
    type=click.Choice(["dummy"], case_sensitive=False),
    default="dummy",
    help="Message source channel",
)
@click.option(
    "--file",
    type=click.Path(exists=True),
    required=True,
    help="Path to message dataset file",
)
@click.option(
    "--day",
    type=int,
    help="Filter messages by day number",
)
@click.option(
    "--validate",
    is_flag=True,
    help="Validate results against expected values",
)
def process(source: str, file: str, day: int, validate: bool):
    """Process messages from a data source."""
    asyncio.run(_process_messages(source, file, day, validate))


async def _process_messages(
    source: str,
    file_path: str,
    day: int,
    validate: bool,
):
    """Async implementation of message processing."""
    console.print(f"\n[bold cyan]LoA Worker - Message Processing[/bold cyan]")
    console.print(f"Source: {source}")
    console.print(f"File: {file_path}")
    if day:
        console.print(f"Day filter: {day}")
    console.print()

    # Initialize components
    llm_service = get_llm_service()
    pre_filter = PreFilter()

    # Connect to Firestore (required)
    try:
        firestore_client = FirestoreClient()
        await firestore_client.connect()
        case_repo = CaseRepository(firestore_client.client)
        audit_repo = AuditRepository(firestore_client.client)
        console.print("[green]✓[/green] Connected to Firestore")
    except Exception as e:
        console.print(f"\n[red]✗ Failed to connect to Firestore[/red]")
        console.print(f"[red]Error: {e}[/red]\n")
        console.print("[yellow]Firestore is required to run the LoA Worker.[/yellow]")
        console.print("\n[dim]Please configure Firestore:[/dim]")
        console.print("[dim]1. Set FIRESTORE_PROJECT_ID in environment[/dim]")
        console.print("[dim]2. Set GOOGLE_APPLICATION_CREDENTIALS path[/dim]")
        console.print("[dim]3. See .env.example for details[/dim]")
        return

    # Initialize pipeline
    orchestrator = PipelineOrchestrator(
        llm_service=llm_service,
        case_repo=case_repo,
        audit_repo=audit_repo,
        pre_filter=pre_filter,
    )

    # Load messages from channel
    async with DummyChannel(file_path=file_path) as channel:
        messages = []
        async for message in channel.fetch_messages(day=day):
            messages.append(message)

        console.print(f"[cyan]Loaded {len(messages)} messages[/cyan]\n")
        batch_result = await orchestrator.process_batch(messages)

        # Display results
        console.print(f"\n[bold green]Processing Complete![/bold green]")
        console.print(f"Total messages: {batch_result.total_messages}")
        console.print(f"Processed: {batch_result.processed}")
        console.print(f"Skipped (irrelevant): {batch_result.skipped}")
        console.print(f"Failed: {batch_result.failed}")
        console.print(f"Success rate: {batch_result.get_success_rate():.1f}%")
        console.print(f"Total time: {batch_result.total_time_ms:.0f}ms")
        console.print(
            f"Avg time per message: {batch_result.total_time_ms / batch_result.total_messages:.0f}ms"
        )

        # Validation
        if validate:
            console.print(f"\n[bold cyan]Validation Results[/bold cyan]")
            validation_results = []

            for i, message in enumerate(messages):
                result = batch_result.results[i]
                validation = await orchestrator.validate_result(message, result)
                validation_results.append(validation)

            passed = sum(1 for v in validation_results if v["passed"])
            failed = len(validation_results) - passed

            console.print(f"Passed: {passed}/{len(validation_results)}")
            console.print(f"Failed: {failed}/{len(validation_results)}")

            if failed > 0:
                console.print("\n[yellow]Failed validations:[/yellow]")
                for v in validation_results:
                    if not v["passed"]:
                        console.print(f"  Message {v['message_id']}:")
                        for error in v["errors"]:
                            console.print(f"    - {error}")

        # Show detailed results table
        _show_results_table(messages, batch_result.results)

    # Cleanup
    await firestore_client.disconnect()


def _show_results_table(messages, results):
    """Display detailed results in a table."""
    table = Table(title="\nDetailed Processing Results", show_lines=True)

    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Category", style="magenta")
    table.add_column("Action", style="green")
    table.add_column("Client", style="yellow")
    table.add_column("Time (ms)", justify="right", style="blue")

    for i, result in enumerate(results):
        message = messages[i]
        category = result.classification.category.value if result.classification else "N/A"
        action = result.actions_taken[0].type.value if result.actions_taken else "NONE"
        client = (
            result.extracted_entities.client_name if result.extracted_entities else "N/A"
        )
        time_ms = f"{result.processing_time_ms:.0f}" if result.processing_time_ms else "N/A"

        table.add_row(message.id, category, action, client, time_ms)

    console.print(table)


@cli.command()
@click.option(
    "--status",
    type=click.Choice(["OPEN", "IN_PROGRESS", "AWAITING_INFO", "COMPLETE", "CANCELLED"]),
    help="Filter by status",
)
@click.option(
    "--type",
    type=click.Choice(["loa", "general", "annual_review"]),
    help="Filter by case type",
)
@click.option(
    "--limit",
    type=int,
    default=20,
    help="Maximum number of cases to show",
)
def cases(status: str, type: str, limit: int):
    """List and view cases."""
    asyncio.run(_list_cases(status, type, limit))


async def _list_cases(status_str: str, type_str: str, limit: int):
    """Async implementation of case listing."""
    console.print(f"\n[bold cyan]Cases List[/bold cyan]\n")

    # Convert string filters to enums
    status_filter = CaseStatus(status_str) if status_str else None
    type_filter = CaseType(type_str) if type_str else None

    # Try to connect to Firestore
    try:
        firestore_client = FirestoreClient()
        await firestore_client.connect()
        case_repo = CaseRepository(firestore_client.client)
        console.print("[green]✓[/green] Connected to Firestore\n")

        # Fetch cases
        cases = await case_repo.list_cases(
            status=status_filter,
            case_type=type_filter,
            limit=limit
        )

        if not cases:
            console.print("[yellow]No cases found.[/yellow]")
            if not status_filter and not type_filter:
                console.print("\n[dim]Tip: Process messages first using:[/dim]")
                console.print("[dim]  loa-worker process --file scenario_full_workflows.json[/dim]")
        else:
            # Display cases in table
            table = Table(title=f"Cases ({len(cases)} found)", show_lines=True)
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Client", style="green")
            table.add_column("Title", style="white")
            table.add_column("Type", style="magenta")
            table.add_column("Status", style="yellow")
            table.add_column("Progress", style="blue", justify="right")
            table.add_column("Updated", style="dim")

            for case in cases:
                progress = f"{case.get_completion_percentage():.0f}%" if case.case_type == CaseType.LOA else "N/A"
                updated = case.updated_at.strftime("%Y-%m-%d %H:%M")

                table.add_row(
                    case.id[:20] + "...",
                    case.client_name,
                    case.case_title[:30] + "..." if len(case.case_title) > 30 else case.case_title,
                    case.case_type.value,
                    case.status.value,
                    progress,
                    updated
                )

            console.print(table)

            # Show summary
            console.print(f"\n[dim]Showing {len(cases)} of {limit} max results[/dim]")

        await firestore_client.disconnect()

    except Exception as e:
        console.print(f"[red]✗[/red] Cannot connect to Firestore: {e}\n")
        console.print("[yellow]The 'cases' command requires Firestore configuration.[/yellow]")
        console.print("\n[dim]To use this command:[/dim]")
        console.print("[dim]1. Configure Firestore (see .env.example)[/dim]")
        console.print("[dim]2. Set FIRESTORE_PROJECT_ID and GOOGLE_APPLICATION_CREDENTIALS[/dim]")
        console.print("[dim]3. Process messages: loa-worker process --file <file>[/dim]")
        console.print("[dim]4. View cases: loa-worker cases[/dim]")


@cli.command()
@click.argument("message_text")
def classify(message_text: str):
    """Test message classification."""
    asyncio.run(_test_classify(message_text))


async def _test_classify(message_text: str):
    """Test classification on a message."""
    from datetime import datetime

    from ..core.models import EmailContent, Message

    console.print(f"\n[bold cyan]Testing Classification[/bold cyan]")
    console.print(f"Message: {message_text}\n")

    # Create mock message
    message = Message(
        id="test",
        timestamp=datetime.utcnow(),
        source_type="email",
        content=EmailContent(
            from_address="test@example.com",
            to_address="test@example.com",
            subject="Test",
            body=message_text,
        ),
    )

    # Classify
    llm_service = get_llm_service()
    classification = await llm_service.classify_message(message)

    console.print(f"Category: [bold]{classification.category.value}[/bold]")
    console.print(f"Confidence: {classification.confidence:.2f}")
    console.print(f"Relevant: {classification.is_relevant}")
    console.print(f"Reasoning: {classification.reasoning}")


@cli.command()
def stats():
    """Show system statistics."""
    console.print("[bold cyan]LoA Worker Statistics[/bold cyan]\n")
    console.print("[yellow]This command requires a live system with Firestore[/yellow]")
    console.print("[yellow]No statistics available in demo mode[/yellow]")


if __name__ == "__main__":
    cli()
