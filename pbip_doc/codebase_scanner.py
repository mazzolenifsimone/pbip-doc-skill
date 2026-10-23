"""
PBIP Codebase Scanner & Lineage Discovery Engine.
Recursively discovers Semantic Models, Reports, and PBIP projects across an entire codebase/workspace.
Resolves report-to-dataset bindings, builds symbol indexes (tables, measures), and maps multi-artifact lineage.
Pure Vanilla Python standard library.
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Optional, Any, Tuple, Union

from .docgen.utils import clean_project_name, sanitize_filename
from .docgen.config import DocGenConfig
from .model_schema import PBIPSemanticModel
from .report_schema import PBIPReportModel


DEFAULT_IGNORED_DIRS = {
    ".git",
    ".github",
    ".vscode",
    ".vs",
    ".idea",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "temp_doc",
    "docs",
    "dist",
    "build",
    "site-packages",
    "bin",
    "obj",
}


@dataclass
class DiscoveredArtifact:
    """Base representation of a discovered artifact in a PBIP repository."""
    name: str
    path: Path
    rel_path: str
    raw_name: str


@dataclass
class DiscoveredModel(DiscoveredArtifact):
    """Represents a discovered Power BI Semantic Model."""
    model_format: str  # "TMDL", "BIM", "UNKNOWN"
    is_standalone_bim: bool = False
    definition_path: Optional[Path] = None
    bound_reports: List[str] = field(default_factory=list)  # Report artifact IDs
    tables: List[str] = field(default_factory=list)
    measures: Dict[str, str] = field(default_factory=dict)  # measure_name -> table_name
    expressions: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    model_obj: Optional[PBIPSemanticModel] = None

    @property
    def artifact_id(self) -> str:
        return self.rel_path.replace("\\", "/")


@dataclass
class DiscoveredReport(DiscoveredArtifact):
    """Represents a discovered Power BI Report."""
    report_format: str  # "PBIR", "LEGACY"
    bound_model_name: Optional[str] = None
    bound_model_path: Optional[Path] = None
    bound_model_id: Optional[str] = None
    is_external_model: bool = False
    dataset_reference: Optional[Dict[str, Any]] = None
    page_names: List[str] = field(default_factory=list)
    report_obj: Optional[PBIPReportModel] = None

    @property
    def artifact_id(self) -> str:
        return self.rel_path.replace("\\", "/")


@dataclass
class DiscoveredPbip(DiscoveredArtifact):
    """Represents a discovered .pbip project file."""
    artifacts_data: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class WorkspaceScanResult:
    """Result of scanning a codebase for PBIP artifacts with full lineage and symbol maps."""
    root_path: Path
    models: Dict[str, DiscoveredModel] = field(default_factory=dict)     # key: artifact_id or unique name
    reports: Dict[str, DiscoveredReport] = field(default_factory=dict)   # key: artifact_id or unique name
    pbips: List[DiscoveredPbip] = field(default_factory=list)

    @property
    def total_artifacts(self) -> int:
        return len(self.models) + len(self.reports)

    def is_single_artifact(self) -> bool:
        """Returns True if the scanned scope represents a single isolated artifact (e.g. 1 model or 1 model + 1 paired report)."""
        if len(self.models) == 1 and len(self.reports) == 0:
            return True
        if len(self.models) == 0 and len(self.reports) == 1:
            return True
        if len(self.models) == 1 and len(self.reports) == 1:
            m = next(iter(self.models.values()))
            r = next(iter(self.reports.values()))
            if r.bound_model_id == m.artifact_id or r.bound_model_name == m.name:
                return True
        return False

    def get_model(self, key_or_name: str) -> Optional[DiscoveredModel]:
        """Looks up a model by artifact_id, name, or raw_name."""
        if key_or_name in self.models:
            return self.models[key_or_name]
        clean_key = clean_project_name(key_or_name).lower()
        norm_key = re.sub(r'[\s_\-]+', '', key_or_name).lower()
        for m in self.models.values():
            if clean_project_name(m.name).lower() == clean_key or m.raw_name.lower() == key_or_name.lower():
                return m
            if Path(m.rel_path).name.lower() == key_or_name.lower():
                return m
            if re.sub(r'[\s_\-]+', '', m.name).lower() == norm_key:
                return m
            if re.sub(r'[\s_\-]+', '', Path(m.rel_path).stem).lower() == norm_key:
                return m
            if re.sub(r'[\s_\-]+', '', Path(m.rel_path).parent.name).lower() == norm_key:
                return m
        return None

    def get_report(self, key_or_name: str) -> Optional[DiscoveredReport]:
        """Looks up a report by artifact_id, name, or raw_name."""
        if key_or_name in self.reports:
            return self.reports[key_or_name]
        clean_key = clean_project_name(key_or_name).lower()
        norm_key = re.sub(r'[\s_\-]+', '', key_or_name).lower()
        for r in self.reports.values():
            if clean_project_name(r.name).lower() == clean_key or r.raw_name.lower() == key_or_name.lower():
                return r
            if Path(r.rel_path).name.lower() == key_or_name.lower():
                return r
            if re.sub(r'[\s_\-]+', '', r.name).lower() == norm_key:
                return r
            if re.sub(r'[\s_\-]+', '', Path(r.rel_path).stem).lower() == norm_key:
                return r
            if re.sub(r'[\s_\-]+', '', Path(r.rel_path).parent.name).lower() == norm_key:
                return r
        return None

    def get_bound_model_for_report(self, report_key_or_name: str) -> Optional[DiscoveredModel]:
        """Resolves the bound local model for a given report."""
        report = self.get_report(report_key_or_name)
        if not report:
            return None
        if report.bound_model_id and report.bound_model_id in self.models:
            return self.models[report.bound_model_id]
        if report.bound_model_name:
            return self.get_model(report.bound_model_name)
        if report.bound_model_path:
            for m in self.models.values():
                if m.path.resolve() == report.bound_model_path.resolve():
                    return m
        return None

    def find_measure(self, measure_name: str, preferred_model: Optional[str] = None) -> List[Tuple[DiscoveredModel, str]]:
        """
        Searches all models in the workspace for a measure by name.
        Returns list of (DiscoveredModel, table_name) tuples.
        If preferred_model is given, matches in that model are returned first.
        """
        results: List[Tuple[DiscoveredModel, str]] = []
        clean_m_name = measure_name.strip("[]'\"").lower()

        if preferred_model:
            pm = self.get_model(preferred_model)
            if pm:
                for m_k, tbl in pm.measures.items():
                    if m_k.strip("[]'\"").lower() == clean_m_name:
                        results.append((pm, tbl))

        for m_id, model in self.models.items():
            if preferred_model and (model.artifact_id == preferred_model or model.name == preferred_model):
                continue
            for m_k, tbl in model.measures.items():
                if m_k.strip("[]'\"").lower() == clean_m_name:
                    results.append((model, tbl))

        return results

    def find_table(self, table_name: str, preferred_model: Optional[str] = None) -> List[DiscoveredModel]:
        """
        Searches all models in the workspace for a table by name.
        If preferred_model is given, it is checked first.
        """
        results: List[DiscoveredModel] = []
        clean_t_name = table_name.strip("'\"[]").lower()

        if preferred_model:
            pm = self.get_model(preferred_model)
            if pm:
                for t in pm.tables:
                    if t.strip("'\"[]").lower() == clean_t_name:
                        results.append(pm)
                        break

        for m_id, model in self.models.items():
            if preferred_model and (model.artifact_id == preferred_model or model.name == preferred_model):
                continue
            for t in model.tables:
                if t.strip("'\"[]").lower() == clean_t_name:
                    results.append(model)
                    break

        return results


class CodebaseScanner:
    """
    Scans a directory tree to discover all PBIP artifacts, resolve report dataset bindings,
    and index tables/measures for cross-artifact documentation navigation.
    """

    def __init__(
        self,
        root_dir: Union[str, Path],
        config: Optional[DocGenConfig] = None,
        ignored_dirs: Optional[Set[str]] = None,
    ):
        self.root_path = Path(root_dir).resolve()
        self.config = config or DocGenConfig()
        self.ignored_dirs = set(DEFAULT_IGNORED_DIRS)
        if ignored_dirs:
            self.ignored_dirs.update(ignored_dirs)

    def scan(self, populate_symbols: bool = True) -> WorkspaceScanResult:
        """
        Executes the discovery pass across the root path.
        """
        result = WorkspaceScanResult(root_path=self.root_path)

        if not self.root_path.exists():
            return result

        # Handle direct artifact target (single .SemanticModel, .Report, or model.bim given as root)
        if self._is_single_direct_target(self.root_path):
            self._process_direct_target(self.root_path, result, populate_symbols=populate_symbols)
            self._resolve_lineage(result)
            return result

        # 1. Discover file and directory artifacts recursively
        model_paths: List[Path] = []
        report_paths: List[Path] = []
        pbip_paths: List[Path] = []
        standalone_bim_paths: List[Path] = []

        for current_root, dirs, files in os.walk(str(self.root_path)):
            current_path = Path(current_root)

            # Filter out ignored directories in-place to avoid descending into them
            dirs[:] = [
                d for d in dirs
                if d.lower() not in self.ignored_dirs
                and not d.startswith(".")
                and not any(d.lower().startswith(ign) for ign in ("doc_", "temp_doc"))
            ]

            # Check if current directory is a SemanticModel or Report
            if current_path.suffix.lower() == ".semanticmodel":
                model_paths.append(current_path)
                dirs.clear()  # Do not descend inside artifact directory
                continue

            if current_path.suffix.lower() == ".report":
                report_paths.append(current_path)
                dirs.clear()  # Do not descend inside artifact directory
                continue

            # Check for PBIP and standalone BIM files
            for file_name in files:
                f_lower = file_name.lower()
                f_path = current_path / file_name

                if f_lower.endswith(".pbip"):
                    pbip_paths.append(f_path)
                elif f_lower == "model.bim":
                    # Only treat as standalone if not inside a .SemanticModel
                    if not any(p.suffix.lower() == ".semanticmodel" for p in f_path.parents):
                        standalone_bim_paths.append(f_path)

        # 2. Ingest Discovered Models
        for m_path in model_paths:
            self._ingest_model_dir(m_path, result, populate_symbols=populate_symbols)

        for bim_path in standalone_bim_paths:
            self._ingest_standalone_bim(bim_path, result, populate_symbols=populate_symbols)

        # 3. Ingest Discovered Reports
        for r_path in report_paths:
            self._ingest_report_dir(r_path, result, populate_symbols=populate_symbols)

        # 4. Ingest Discovered PBIP files
        for p_path in pbip_paths:
            self._ingest_pbip_file(p_path, result)

        # 5. Resolve Lineage & Bindings
        self._resolve_lineage(result)

        return result

    def _is_single_direct_target(self, path: Path) -> bool:
        """Determines if the root path itself is an individual model or report."""
        if path.is_file():
            if path.suffix.lower() in (".pbip", ".bim") or path.name.lower() in ("model.bim", "report.json"):
                return True
        elif path.is_dir():
            s = path.suffix.lower()
            if s in (".semanticmodel", ".report"):
                return True
            if (path / "model.bim").is_file():
                return True
            if (path / "definition" / "model.tmdl").is_file() or (path / "model.tmdl").is_file():
                return True
            if (path / "definition.pbir").is_file() or (path / "report.json").is_file():
                return True
        return False

    def _process_direct_target(self, path: Path, result: WorkspaceScanResult, populate_symbols: bool):
        """Processes a single target directly provided as root."""
        if path.is_file():
            if path.suffix.lower() == ".pbip":
                self._ingest_pbip_file(path, result)
                # Also inspect siblings of the pbip
                parent = path.parent
                for child in parent.iterdir():
                    if child.is_dir() and child.suffix.lower() == ".semanticmodel":
                        self._ingest_model_dir(child, result, populate_symbols=populate_symbols)
                    elif child.is_dir() and child.suffix.lower() == ".report":
                        self._ingest_report_dir(child, result, populate_symbols=populate_symbols)
            elif path.name.lower() == "model.bim":
                self._ingest_standalone_bim(path, result, populate_symbols=populate_symbols)
            elif path.name.lower() == "report.json":
                self._ingest_report_dir(path.parent, result, populate_symbols=populate_symbols)
        else:
            s = path.suffix.lower()
            if s == ".semanticmodel" or (path / "model.bim").is_file() or (path / "definition" / "model.tmdl").is_file():
                self._ingest_model_dir(path, result, populate_symbols=populate_symbols)
            elif s == ".report" or (path / "definition.pbir").is_file() or (path / "report.json").is_file():
                self._ingest_report_dir(path, result, populate_symbols=populate_symbols)

    def _ingest_model_dir(self, model_path: Path, result: WorkspaceScanResult, populate_symbols: bool):
        raw_name = model_path.name
        clean_name = clean_project_name(model_path.stem)
        try:
            rel_path = str(model_path.relative_to(self.root_path))
        except ValueError:
            rel_path = model_path.name

        # Detect format
        model_format = "TMDL"
        def_path = model_path / "definition"
        if not def_path.exists():
            def_path = model_path

        if (model_path / "model.bim").is_file() and not (def_path / "model.tmdl").is_file():
            model_format = "BIM"

        discovered = DiscoveredModel(
            name=clean_name,
            path=model_path,
            rel_path=rel_path,
            raw_name=raw_name,
            model_format=model_format,
            is_standalone_bim=False,
            definition_path=def_path if def_path.exists() else None,
        )

        if populate_symbols:
            self._populate_model_symbols(discovered)

        # Unique key
        key = discovered.artifact_id or clean_name
        result.models[key] = discovered

    def _ingest_standalone_bim(self, bim_path: Path, result: WorkspaceScanResult, populate_symbols: bool):
        parent = bim_path.parent
        raw_name = parent.name if parent != self.root_path else bim_path.stem
        clean_name = clean_project_name(raw_name)
        try:
            rel_path = str(bim_path.relative_to(self.root_path))
        except ValueError:
            rel_path = bim_path.name

        discovered = DiscoveredModel(
            name=clean_name,
            path=bim_path,
            rel_path=rel_path,
            raw_name=raw_name,
            model_format="BIM",
            is_standalone_bim=True,
            definition_path=bim_path,
        )

        if populate_symbols:
            self._populate_model_symbols(discovered)

        key = discovered.artifact_id or clean_name
        result.models[key] = discovered

    def _ingest_report_dir(self, report_path: Path, result: WorkspaceScanResult, populate_symbols: bool):
        raw_name = report_path.name
        clean_name = clean_project_name(report_path.stem)
        try:
            rel_path = str(report_path.relative_to(self.root_path))
        except ValueError:
            rel_path = report_path.name

        # Detect format
        report_format = "PBIR"
        if (report_path / "report.json").is_file() and not (report_path / "definition" / "pages").exists():
            report_format = "LEGACY"

        # Check definition.pbir for datasetReference
        ds_ref, bound_model_name, is_external = self._inspect_pbir(report_path)

        discovered = DiscoveredReport(
            name=clean_name,
            path=report_path,
            rel_path=rel_path,
            raw_name=raw_name,
            report_format=report_format,
            bound_model_name=bound_model_name,
            is_external_model=is_external,
            dataset_reference=ds_ref,
        )

        if populate_symbols:
            self._populate_report_symbols(discovered)

        key = discovered.artifact_id or clean_name
        result.reports[key] = discovered

    def _ingest_pbip_file(self, pbip_path: Path, result: WorkspaceScanResult):
        raw_name = pbip_path.name
        clean_name = clean_project_name(pbip_path.stem)
        try:
            rel_path = str(pbip_path.relative_to(self.root_path))
        except ValueError:
            rel_path = pbip_path.name

        artifacts_data: List[Dict[str, Any]] = []
        try:
            with open(pbip_path, "r", encoding="utf-8") as f:
                content = json.load(f)
            if isinstance(content, dict) and "artifacts" in content:
                artifacts_data = content["artifacts"]
        except Exception:
            pass

        discovered = DiscoveredPbip(
            name=clean_name,
            path=pbip_path,
            rel_path=rel_path,
            raw_name=raw_name,
            artifacts_data=artifacts_data,
        )
        result.pbips.append(discovered)

    def _inspect_pbir(self, report_dir: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str], bool]:
        """Inspects definition.pbir to extract datasetReference."""
        candidates = [
            report_dir / "definition.pbir",
            report_dir / "definition" / "definition.pbir",
            report_dir.parent / f"{report_dir.stem}.pbir",
        ]
        pbir_file = next((c for c in candidates if c.is_file()), None)
        if not pbir_file:
            return None, None, False

        try:
            with open(pbir_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            ds_ref = data.get("datasetReference")
            if not isinstance(ds_ref, dict):
                return None, None, False

            by_path = ds_ref.get("byPath")
            if isinstance(by_path, dict) and "path" in by_path:
                rel = by_path["path"]
                stem = Path(rel).stem or Path(rel).name
                return ds_ref, clean_project_name(stem), False

            by_conn = ds_ref.get("byConnection")
            if isinstance(by_conn, dict):
                model_name = by_conn.get("pbiModelDatabaseName")
                if not model_name:
                    conn_str = by_conn.get("connectionString", "")
                    m = re.search(r'Initial\s+Catalog\s*=\s*([^;]+)', conn_str, re.IGNORECASE)
                    if m:
                        model_name = m.group(1).strip()
                if model_name:
                    return ds_ref, clean_project_name(model_name), True
                return ds_ref, "Remote Semantic Model", True

            return ds_ref, None, False
        except Exception:
            return None, None, False

    def _populate_model_symbols(self, model: DiscoveredModel):
        """Extracts tables, measures, functions, and expressions into model index."""
        scoped_cfg = self.config.get_scoped_config(model.artifact_id)
        try:
            from .parser import PBIPParser
            parser = PBIPParser(config=scoped_cfg)
            parsed_model = parser.parse(str(model.path), config=scoped_cfg)
            model.model_obj = parsed_model
            model.tables = [t.name for t in parsed_model.tables if not scoped_cfg.is_table_excluded(t.name)]
            model.measures = {
                m.name: (m.table if hasattr(m, 'table') else getattr(m, 'table_name', ''))
                for m in parsed_model.measures
                if not scoped_cfg.is_table_excluded(getattr(m, 'table', getattr(m, 'table_name', '')))
            }
            model.expressions = [
                getattr(e, 'name', getattr(e, 'query_name', ''))
                for e in parsed_model.expressions
            ]
            model.functions = [getattr(f, 'name', '') for f in parsed_model.functions]
        except Exception:
            # Fallback to lightweight filesystem inspection if full parse fails
            if model.model_format == "TMDL":
                tables_dir = (model.definition_path or model.path) / "tables"
                if tables_dir.is_dir():
                    model.tables = [
                        f.stem for f in tables_dir.glob("*.tmdl")
                        if not scoped_cfg.is_table_excluded(f.stem)
                    ]
            elif model.path.is_file() and model.path.suffix.lower() == ".bim":
                try:
                    with open(model.path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    m = data.get("model", {})
                    model.tables = [
                        t.get("name") for t in m.get("tables", [])
                        if t.get("name") and not scoped_cfg.is_table_excluded(t.get("name"))
                    ]
                except Exception:
                    pass

    def _populate_report_symbols(self, report: DiscoveredReport):
        """Extracts report page names and optionally parses presentation model."""
        try:
            from .report_parser import ReportParser
            parser = ReportParser()
            parsed_report = parser.parse(str(report.path))
            report.report_obj = parsed_report
            report.page_names = [p.display_name for p in parsed_report.pages]
        except Exception:
            # Fallback: inspect pages directory in PBIR
            pages_dir = report.path / "definition" / "pages"
            if pages_dir.is_dir():
                for p_dir in pages_dir.iterdir():
                    if p_dir.is_dir() and (p_dir / "page.json").is_file():
                        try:
                            with open(p_dir / "page.json", "r", encoding="utf-8") as f:
                                pj = json.load(f)
                            report.page_names.append(pj.get("displayName", p_dir.name))
                        except Exception:
                            report.page_names.append(p_dir.name)

    def _resolve_lineage(self, result: WorkspaceScanResult):
        """Resolves report-to-model bindings and cross-references."""
        # 1. Match Reports via datasetReference
        for report in result.reports.values():
            resolved_model: Optional[DiscoveredModel] = None

            if report.dataset_reference:
                by_path = report.dataset_reference.get("byPath")
                if isinstance(by_path, dict) and "path" in by_path:
                    raw_rel = by_path["path"]
                    # Try resolving relative path from report dir
                    target_path = (report.path / raw_rel).resolve()
                    for m in result.models.values():
                        if m.path.resolve() == target_path:
                            resolved_model = m
                            break

                    # Fallback: check matching stem / name
                    if not resolved_model:
                        stem = clean_project_name(Path(raw_rel).stem)
                        for m in result.models.values():
                            if clean_project_name(m.name).lower() == stem.lower() or m.raw_name.lower() == Path(raw_rel).name.lower():
                                resolved_model = m
                                break

            # 2. Sibling / PBIP matching if still unresolved
            if not resolved_model:
                # Check if there is a model in the same parent directory with matching name
                for m in result.models.values():
                    if m.path.parent == report.path.parent:
                        if clean_project_name(m.name).lower() == clean_project_name(report.name).lower():
                            resolved_model = m
                            break

            # 3. Apply resolved binding
            if resolved_model:
                report.bound_model_name = resolved_model.name
                report.bound_model_path = resolved_model.path
                report.bound_model_id = resolved_model.artifact_id
                report.is_external_model = False
                if report.artifact_id not in resolved_model.bound_reports:
                    resolved_model.bound_reports.append(report.artifact_id)
            else:
                if report.bound_model_name:
                    # Model not present in local workspace
                    report.is_external_model = True
