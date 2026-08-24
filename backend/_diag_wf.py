"""Pinpoint where a workflow step hangs. Runs each stage in a watchdog thread."""
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.sandbox")
import django  # noqa: E402
django.setup()
import threading  # noqa: E402
from apps.workflows.models import WorkflowRun, WorkflowStep, WorkflowStepRun  # noqa: E402
from apps.workflows.executors import get_executor  # noqa: E402
from apps.workflows.services import member_for_run  # noqa: E402
from apps.tenancy.models import Workspace  # noqa: E402

ws = Workspace.objects.get(slug="sridhar-school-4")
sr = WorkflowStepRun.objects.filter(workspace_id=ws.id, status="pending").first()
if not sr:
    print("no pending step run")
    raise SystemExit

run = WorkflowRun.objects.get(id=sr.run_id)
step = WorkflowStep.objects.get(id=sr.step_id)
print(f"step type={step.step_type} name={getattr(step,"name","")} run={run.id}")


def stage(name, fn):
    result = {}

    def target():
        try:
            result["v"] = fn()
        except Exception as e:  # noqa: BLE001
            result["err"] = repr(e)

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout=8)
    if t.is_alive():
        print(f"  [HANG] {name} did not finish in 8s  <-- blocks here")
        return "HANG"
    if "err" in result:
        print(f"  [ERR ] {name}: {result['err']}")
        return None
    print(f"  [ ok ] {name}")
    return result.get("v")


ctx = dict(run.context or {})
ctx["__step_run_id__"] = str(sr.id)
member = stage("member_for_run", lambda: member_for_run(run))
executor = stage("get_executor", lambda: get_executor(step.step_type))
if executor and executor != "HANG":
    stage("executor(step,run,ctx,member)", lambda: executor(step, run, ctx, member))
print("done")
