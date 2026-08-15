"""REQ-24: golden structural validation + sqcli -h readiness probe; deviation
fails closed with a ValidationError naming the deviating element; no dispatch."""

from __future__ import annotations

from pathlib import Path

import pytest

from quantlab.customproject.generator import generate_cfx_archive
from quantlab.customproject.models import (
    CustomProject,
    CustomProjectTask,
    DatabankSpec,
    GoToTask,
)
from quantlab.customproject.validator import (
    ValidationError,
    resolve_sqcli,
    validate_golden,
)
from quantlab.cfx.models import CfxProject

REPO_ROOT = Path(__file__).resolve().parents[2]
SQX_ROOT = Path.home() / "Proyectos" / "SQX_144_2953_linux_20260601"

STANDARD_DATABANKS = [
    DatabankSpec(name="Results"),
    DatabankSpec(name="Last generation"),
    DatabankSpec(name="Initial population"),
    DatabankSpec(name="Strategies to improve"),
]


def _probe_ok() -> bool:
    return True


def _four_task_project() -> CustomProject:
    return CustomProject(
        name="four-task",
        tasks=[
            CustomProjectTask(type="Build", name="Build"),
            CustomProjectTask(type="Filtering", name="Filtering"),
            CustomProjectTask(type="Retest", name="Retest"),
            CustomProjectTask(
                type="GoToTask",
                name="GoToTask",
                goto=GoToTask(target="Filtering", condition="retest_failed"),
            ),
        ],
        databanks=STANDARD_DATABANKS,
    )


class TestGoldenValidation:
    """REQ-24: valid archives pass; deviations raise ValidationError."""

    def test_valid_four_task_archive_passes(self):
        archive = generate_cfx_archive(_four_task_project())
        # probe injected: fast unit test; the real sqcli -h gate runs in E2E.
        result = validate_golden(archive, SQX_ROOT, probe_runner=_probe_ok)
        assert result is None

    def test_valid_single_task_passes(self):
        project = CustomProject(
            name="single",
            tasks=[CustomProjectTask(type="Build", name="Build")],
            databanks=STANDARD_DATABANKS,
        )
        archive = generate_cfx_archive(project)
        assert validate_golden(archive, SQX_ROOT, probe_runner=_probe_ok) is None

    def test_schema_version_deviation_fails_closed(self):
        project = CustomProject(
            name="wrongver",
            tasks=[CustomProjectTask(type="Build", name="Build")],
            databanks=STANDARD_DATABANKS,
            schema_version="999.1",
        )
        archive = generate_cfx_archive(project)
        with pytest.raises(ValidationError) as exc:
            validate_golden(archive, SQX_ROOT, probe_runner=_probe_ok)
        assert "version" in str(exc.value).lower()

    def test_missing_tasks_section_fails_closed(self):
        # A Project config with no <Tasks> element at all.
        archive = _archive_from_project(CfxProject(name="no-tasks", tasks={}, schema_version="144.2953"))
        with pytest.raises(ValidationError) as exc:
            validate_golden(archive, SQX_ROOT, probe_runner=_probe_ok)
        assert "Tasks" in str(exc.value)

    def test_task_without_type_fails_closed_naming_element(self):
        # Constructed at the CfxProject level (as a faulty renderer would):
        # a packaged task whose <Task> element carries an empty type.
        project = CfxProject(
            name="notype",
            tasks={"Build-Task1.xml": _task_noop()},
            schema_version="144.2953",
            databanks=STANDARD_DATABANKS,
            task_meta={"Build-Task1.xml": _meta(task_type="")},
        )
        archive = _archive_from_project(project)
        with pytest.raises(ValidationError) as exc:
            validate_golden(archive, SQX_ROOT, probe_runner=_probe_ok)
        assert "Tasks" in str(exc.value) and "Task" in str(exc.value)

    def test_missing_databanks_section_fails_closed_naming_element(self):
        project = CustomProject(
            name="nodb",
            tasks=[CustomProjectTask(type="Build", name="Build")],
            databanks=[],
        )
        archive = generate_cfx_archive(project)
        with pytest.raises(ValidationError) as exc:
            validate_golden(archive, SQX_ROOT, probe_runner=_probe_ok)
        assert "Databanks" in str(exc.value)

    def test_databank_without_name_fails_closed(self):
        project = CustomProject(
            name="noname",
            tasks=[CustomProjectTask(type="Build", name="Build")],
            databanks=[DatabankSpec(name="")],
        )
        archive = generate_cfx_archive(project)
        with pytest.raises(ValidationError) as exc:
            validate_golden(archive, SQX_ROOT, probe_runner=_probe_ok)
        assert "Databank" in str(exc.value)


class TestProbe:
    """REQ-24: sqcli -h readiness probe runs before validation."""

    def test_probe_failure_blocks_validation(self):
        archive = generate_cfx_archive(_four_task_project())

        def probe_fails() -> bool:
            return False

        with pytest.raises(ValidationError) as exc:
            validate_golden(archive, SQX_ROOT, probe_runner=probe_fails)
        assert "sqcli" in str(exc.value).lower()

    def test_probe_runs_before_structural_validation(self):
        """Even a malformed archive raises the probe error first (probe SHALL
        run before validation per REQ-24)."""
        archive = _archive_from_project(
            CfxProject(name="bad", tasks={}, schema_version="144.2953")
        )

        calls: list[str] = []

        def probe() -> bool:
            calls.append("probe")
            return False

        with pytest.raises(ValidationError):
            validate_golden(archive, SQX_ROOT, probe_runner=probe)
        assert calls == ["probe"]


class TestNoDispatchOnDeviation:
    """REQ-24: deviation → ValidationError, and no dispatch is attempted."""

    def test_dispatch_never_called_on_deviation(self):
        project = CustomProject(
            name="noname-db",
            tasks=[CustomProjectTask(type="Build", name="Build")],
            databanks=[DatabankSpec(name="")],
        )
        archive = generate_cfx_archive(project)

        dispatched: list[str] = []

        def dispatch(action: str, target: str) -> None:
            dispatched.append(f"{action}:{target}")

        # Mirror the real flow: validate first, dispatch only if valid.
        try:
            validate_golden(archive, SQX_ROOT, probe_runner=_probe_ok)
        except ValidationError:
            pass
        else:
            dispatch("loadconfig", "four-task")

        assert dispatched == []

    def test_valid_archive_does_dispatch(self):
        archive = generate_cfx_archive(_four_task_project())

        dispatched: list[str] = []

        def dispatch(action: str, target: str) -> None:
            dispatched.append(f"{action}:{target}")

        try:
            validate_golden(archive, SQX_ROOT, probe_runner=_probe_ok)
        except ValidationError:
            dispatched.append("validation-failed")
        else:
            dispatch("loadconfig", "four-task")

        assert dispatched == ["loadconfig:four-task"]


class TestResolveSqcli:
    def test_resolves_from_sqx_root(self):
        path = resolve_sqcli(SQX_ROOT)
        assert path == SQX_ROOT / "sqcli"

    def test_env_var_takes_precedence(self, monkeypatch):
        fake = SQX_ROOT / "sqcli"
        monkeypatch.setenv("SQCLI_PATH", str(fake))
        assert resolve_sqcli(Path("/nonexistent")) == fake

    def test_missing_binary_raises_validation_error(self, monkeypatch):
        from quantlab.customproject import validator as validator_mod

        monkeypatch.setattr(validator_mod, "DEFAULT_SQCLI", Path("/no/such/sqcli"))
        with pytest.raises(ValidationError):
            resolve_sqcli(Path("/does/not/exist"), env={"SQCLI_PATH": "/no/such/sqcli"})


def _archive_from_project(project: CfxProject):
    """Wrap a CfxProject into a CfxArchive (the model the validator inspects)."""
    from quantlab.cfx.models import CfxArchive

    return CfxArchive(config=project, task_files=dict(project.tasks))


def _task_noop():
    from quantlab.cfx.models import BuildTask

    return BuildTask()


def _meta(task_type: str = "Build", name: str = "Build", active: bool = True):
    from quantlab.cfx.models import TaskMeta

    return TaskMeta(task_type=task_type, name=name, active=active)
