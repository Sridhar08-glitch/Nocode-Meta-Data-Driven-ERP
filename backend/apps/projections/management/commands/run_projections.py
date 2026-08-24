"""Drain the event stream into read models (audit, etc.). Use --rebuild to replay all."""
from django.core.management.base import BaseCommand

from apps.projections.services import rebuild_projection, run_projections


class Command(BaseCommand):
    help = "Run projection consumers over the domain_events stream."

    def add_arguments(self, parser):
        parser.add_argument("--projection", default="default")
        parser.add_argument("--rebuild", action="store_true",
                            help="Reset the checkpoint and replay the entire stream.")

    def handle(self, *args, **opts):
        name = opts["projection"]
        if opts["rebuild"]:
            n = rebuild_projection(projection_name=name)
            self.stdout.write(self.style.SUCCESS(f"Rebuilt {name!r}: {n} events replayed."))
        else:
            n = run_projections(projection_name=name)
            self.stdout.write(self.style.SUCCESS(f"Projected {n} new event(s) into {name!r}."))
