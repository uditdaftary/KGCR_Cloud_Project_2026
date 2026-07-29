"""Generate the two mandatory architecture diagrams as PNG and SVG.

Diagram 1 (AWS Cloud Architecture) is the planned service topology from PMD section 6.
Diagram 2 (Complete System Architecture) is the unified flow from FD-01.

    python architecture/make_diagrams.py

Both diagrams are generated rather than drawn by hand so a design change is a diff in this
file rather than an opaque binary. Layout code emits backend-neutral primitives; a PNG
renderer (Pillow) and an SVG renderer walk the same list, so the two outputs cannot drift.
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent

INK = (26, 26, 26)
MUTED = (107, 107, 107)
WHITE = (255, 255, 255)
FILL_GROUP = (245, 245, 244)
FILL_BOX = WHITE
FILL_STORE = (238, 242, 246)
FILL_ACCENT = (232, 238, 244)

FONT_REGULAR = "C:/Windows/Fonts/segoeui.ttf"
FONT_BOLD = "C:/Windows/Fonts/segoeuib.ttf"
SCALE = 2  # PNG supersampling factor, for a crisp raster at report resolution


def rgb(c: tuple[int, int, int]) -> str:
    return f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}"


class Canvas:
    """Collects backend-neutral primitives, then renders PNG and SVG from the same list."""

    def __init__(self, width: int, height: int) -> None:
        self.w, self.h = width, height
        self.items: list[tuple] = []

    # -- primitives ---------------------------------------------------------------------
    def rect(self, x, y, w, h, *, fill=FILL_BOX, stroke=INK, dashed=False, radius=4) -> None:
        self.items.append(("rect", x, y, w, h, fill, stroke, dashed, radius))

    def text(self, x, y, s, *, size=13, anchor="middle", bold=False, fill=INK) -> None:
        self.items.append(("text", x, y, s, size, anchor, bold, fill))

    def line(self, x1, y1, x2, y2, *, arrow=True) -> None:
        self.items.append(("line", x1, y1, x2, y2, arrow))

    # -- composites ---------------------------------------------------------------------
    def box(self, x, y, w, h, lines, *, fill=FILL_BOX, dashed=False, size=13, bold=False) -> None:
        self.rect(x, y, w, h, fill=fill, dashed=dashed)
        step = size + 4
        top = y + h / 2 - (len(lines) - 1) * step / 2
        for i, line in enumerate(lines):
            self.text(x + w / 2, top + i * step, line, size=size, bold=bold)

    def group(self, x, y, w, h, title) -> None:
        self.rect(x, y, w, h, fill=FILL_GROUP, stroke=MUTED, dashed=True, radius=6)
        self.text(x + 12, y + 16, title, size=13, anchor="start", bold=True, fill=MUTED)

    def arrow(self, x1, y1, x2, y2, label="", *, lx=None, ly=None) -> None:
        self.line(x1, y1, x2, y2)
        if label:
            self.text(
                lx if lx is not None else (x1 + x2) / 2,
                ly if ly is not None else (y1 + y2) / 2 - 9,
                label,
                size=11,
                fill=MUTED,
            )

    def elbow(self, x1, y1, x2, y2, label="") -> None:
        """Right-angle connector: horizontal from the source, then vertical into the target."""
        self.line(x1, y1, x2, y1, arrow=False)
        self.line(x2, y1, x2, y2)
        if label:
            self.text((x1 + x2) / 2, y1 - 9, label, size=11, fill=MUTED)

    def path(self, points, label="", *, lx=None, ly=None) -> None:
        """Polyline through ``points``; the arrowhead lands on the final segment.

        Used to route long connectors around boxes instead of cutting across them.
        """
        for i in range(len(points) - 1):
            (x1, y1), (x2, y2) = points[i], points[i + 1]
            self.line(x1, y1, x2, y2, arrow=(i == len(points) - 2))
        if label:
            self.text(
                lx if lx is not None else points[0][0],
                ly if ly is not None else points[0][1] - 9,
                label,
                size=11,
                fill=MUTED,
            )

    # -- renderers ----------------------------------------------------------------------
    def to_png(self, path: Path) -> None:
        s = SCALE
        img = Image.new("RGB", (self.w * s, self.h * s), WHITE)
        d = ImageDraw.Draw(img)
        fonts: dict[tuple[int, bool], ImageFont.FreeTypeFont] = {}

        def font(size: int, bold: bool) -> ImageFont.FreeTypeFont:
            key = (size, bold)
            if key not in fonts:
                fonts[key] = ImageFont.truetype(FONT_BOLD if bold else FONT_REGULAR, size * s)
            return fonts[key]

        for it in self.items:
            kind = it[0]
            if kind == "rect":
                _, x, y, w, h, fill, stroke, dashed, radius = it
                d.rounded_rectangle(
                    [x * s, y * s, (x + w) * s, (y + h) * s],
                    radius=radius * s,
                    fill=fill,
                    outline=stroke,
                    width=max(1, s),
                )
            elif kind == "text":
                _, x, y, txt, size, anchor, bold, fill = it
                d.text(
                    (x * s, y * s),
                    txt,
                    font=font(size, bold),
                    fill=fill,
                    anchor={"middle": "mm", "start": "lm"}[anchor],
                )
            elif kind == "line":
                _, x1, y1, x2, y2, has_arrow = it
                d.line([x1 * s, y1 * s, x2 * s, y2 * s], fill=INK, width=max(1, s))
                if has_arrow:
                    self._png_arrowhead(d, x1 * s, y1 * s, x2 * s, y2 * s, 7 * s)
        img.resize((self.w, self.h), Image.LANCZOS).save(path)

    @staticmethod
    def _png_arrowhead(
        d: ImageDraw.ImageDraw, x1: float, y1: float, x2: float, y2: float, size: float
    ) -> None:
        import math

        angle = math.atan2(y2 - y1, x2 - x1)
        spread = math.radians(24)
        p1 = (x2 - size * math.cos(angle - spread), y2 - size * math.sin(angle - spread))
        p2 = (x2 - size * math.cos(angle + spread), y2 - size * math.sin(angle + spread))
        d.polygon([(x2, y2), p1, p2], fill=INK)

    def to_svg(self, path: Path) -> None:
        out = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}" font-family="Segoe UI, Helvetica, Arial, '
            'sans-serif">',
            f'<rect width="{self.w}" height="{self.h}" fill="#ffffff"/>',
            '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
            f'markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" '
            f'fill="{rgb(INK)}"/></marker></defs>',
        ]
        for it in self.items:
            kind = it[0]
            if kind == "rect":
                _, x, y, w, h, fill, stroke, dashed, radius = it
                dash = ' stroke-dasharray="6 4"' if dashed else ""
                out.append(
                    f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
                    f'fill="{rgb(fill)}" stroke="{rgb(stroke)}" stroke-width="1.2"{dash}/>'
                )
            elif kind == "text":
                _, x, y, txt, size, anchor, bold, fill = it
                a = "middle" if anchor == "middle" else "start"
                weight = ' font-weight="bold"' if bold else ""
                out.append(
                    f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{a}" '
                    f'dominant-baseline="central" fill="{rgb(fill)}"{weight}>'
                    f"{escape(txt)}</text>"
                )
            elif kind == "line":
                _, x1, y1, x2, y2, has_arrow = it
                marker = ' marker-end="url(#a)"' if has_arrow else ""
                out.append(
                    f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{rgb(INK)}" '
                    f'stroke-width="1.4"{marker}/>'
                )
        out.append("</svg>")
        path.write_text("\n".join(out), encoding="utf-8")


def aws_architecture() -> Canvas:
    c = Canvas(1500, 940)
    c.text(
        40, 40, "Diagram 1 — AWS Cloud Architecture (planned)", size=21, anchor="start", bold=True
    )
    c.text(
        40,
        66,
        "KGCR: three-account topology, evidence pipeline and analysis plane "
        "(PMD section 6, FD-08)",
        size=13,
        anchor="start",
        fill=MUTED,
    )

    c.group(40, 96, 340, 470, "Account A — prod-payments (estate under analysis)")
    c.box(64, 132, 292, 54, ["Amazon VPC — subnets, route tables,", "security groups, NAT / IGW"])
    c.box(64, 200, 292, 46, ["Amazon EC2 / ECS", "application workload"])
    c.box(64, 260, 292, 46, ["Amazon RDS", "cardholder data store"], fill=FILL_STORE)
    c.box(64, 320, 292, 46, ["Amazon S3", "object storage"], fill=FILL_STORE)
    c.box(64, 380, 292, 46, ["AWS KMS", "encryption keys"])
    c.box(64, 440, 292, 46, ["AWS IAM", "roles, policies, trust relationships"])
    c.box(64, 500, 292, 46, ["Elastic Load Balancing"])

    c.group(40, 590, 340, 120, "Account B — dev-staging (drift comparison)")
    c.box(
        64,
        622,
        292,
        62,
        ["Divergent copy of Account A", "same resource types, drifted configuration"],
        dashed=True,
    )

    c.group(415, 96, 300, 614, "Evidence collection and processing")
    c.box(437, 132, 256, 46, ["AWS Config", "resource inventory + relationships"])
    c.box(437, 192, 256, 46, ["AWS CloudTrail", "API audit events"])
    c.box(437, 252, 256, 46, ["Cost & Usage Reports", "cost attribution per resource"])
    c.box(
        437,
        330,
        256,
        54,
        ["Amazon S3", "evidence landing bucket", "(versioned, SSE-KMS)"],
        fill=FILL_STORE,
    )
    c.box(
        437,
        424,
        256,
        54,
        ["AWS Lambda / AWS Glue", "ETL: normalise to the L2 graph schema"],
        fill=FILL_ACCENT,
    )
    c.box(437, 518, 256, 46, ["Amazon EventBridge", "scheduled + change-driven triggers"])
    c.box(
        437,
        590,
        256,
        100,
        [
            "Amazon CloudWatch",
            "logs, metrics, alarms",
            "— monitoring —",
            "AWS Budgets cost alarms (FD-08)",
        ],
    )

    c.group(750, 96, 380, 614, "Account C — shared-security (analysis platform)")
    c.box(
        774,
        132,
        332,
        62,
        [
            "Neo4j Community on Amazon EC2",
            "knowledge graph: L1 controls,",
            "L2 estate, L3 run records",
        ],
        fill=FILL_ACCENT,
    )
    c.box(774, 214, 332, 54, ["Amazon SageMaker", "train recommender + intent reconstructor"])
    c.box(774, 288, 332, 54, ["AWS Lambda", "Advisor / Explainer inference"])
    c.box(774, 362, 332, 54, ["Amazon Bedrock", "intent extraction and verbalisation only"])
    c.box(774, 436, 332, 46, ["Amazon API Gateway", "REST surface for the kgcr CLI"])
    c.box(774, 496, 332, 46, ["Amazon Cognito", "user authentication"])
    c.box(774, 556, 332, 46, ["AWS IAM", "cross-account read / write role split"])
    c.box(774, 616, 332, 46, ["Amazon SNS", "findings and budget notifications"])

    c.group(1165, 96, 295, 350, "Users and outputs")
    c.box(1187, 132, 251, 54, ["kgcr CLI", "design / review / explain"])
    c.box(
        1187,
        206,
        251,
        62,
        ["Architect / Auditor / Learner", "audience-relative rendering", "of the same conclusion"],
    )
    c.box(1187, 288, 251, 54, ["Terraform plan / apply", "Agent 1 (write-only role)"])
    c.box(1187, 362, 251, 62, ["Evidence export", "OSCAL / attestation artefacts"], fill=FILL_STORE)

    c.arrow(380, 223, 437, 155, "harvest", lx=406, ly=196)
    c.arrow(380, 283, 437, 215)
    c.arrow(380, 343, 437, 275)
    c.arrow(380, 653, 437, 366, "drift baseline", lx=404, ly=576)
    c.arrow(565, 178, 565, 330)
    c.arrow(565, 298, 565, 330)
    c.arrow(565, 384, 565, 424, "extract")
    c.arrow(565, 478, 565, 518, "load")
    c.arrow(693, 451, 774, 182, "L2 graph load", lx=742, ly=300)
    c.arrow(1130, 163, 1187, 159, "query", lx=1158, ly=146)
    c.arrow(1130, 459, 1187, 245, "results", lx=1152, ly=350)
    c.arrow(1130, 639, 1187, 330, "notify", lx=1152, ly=490)
    c.arrow(693, 620, 774, 620, "metrics")
    # Long connectors route around the account groups rather than cutting across them.
    c.path(
        [(1313, 342), (1313, 726), (1000, 726), (1000, 604)],
        "Agent 1 assumes the write role",
        lx=1140,
        ly=740,
    )
    c.path(
        [(886, 602), (886, 752), (210, 752), (210, 566)],
        "cross-account read — Agent 2, read-only",
        lx=548,
        ly=766,
    )

    c.text(40, 800, "Legend", size=14, anchor="start", bold=True)
    c.text(
        40,
        824,
        "Solid box = AWS service.   Shaded box = data store.   "
        "Dashed container = AWS account boundary.",
        size=12,
        anchor="start",
        fill=MUTED,
    )
    c.text(
        40,
        846,
        "Authentication: Amazon Cognito for users; AWS IAM cross-account roles for the "
        "agents (Agent 2 read-only, Agent 1 write-only).",
        size=12,
        anchor="start",
        fill=MUTED,
    )
    c.text(
        40,
        868,
        "Monitoring: Amazon CloudWatch logs, metrics and alarms; AWS Budgets alarms "
        "live from day one (FD-08).   Notifications: Amazon SNS.",
        size=12,
        anchor="start",
        fill=MUTED,
    )
    c.text(
        40,
        898,
        "Status — this is a Phase-I planning diagram. Implemented today: the AWS "
        "Budgets and cross-account IAM Terraform in src/aws/ (authored, not applied). "
        "Everything else is the Phase-II",
        size=12,
        anchor="start",
    )
    c.text(
        40,
        920,
        "build target; the analysis pipeline currently runs locally in Python under "
        "src/backend/.",
        size=12,
        anchor="start",
    )
    return c


def system_architecture() -> Canvas:
    c = Canvas(1400, 1010)
    c.text(40, 40, "Diagram 2 — Complete System Architecture", size=21, anchor="start", bold=True)
    c.text(
        40,
        66,
        "KGCR unified flow: one pipeline, two entry conditions " "(FD-01, stages S1 to S10)",
        size=13,
        anchor="start",
        fill=MUTED,
    )

    c.box(
        80,
        110,
        300,
        66,
        [
            "Condition 1 — Design",
            '"design me a config for..."',
            "user states intent in business terms",
        ],
        fill=FILL_ACCENT,
    )
    c.box(
        1020,
        110,
        300,
        66,
        [
            "Condition 2 — Review",
            '"what is wrong with my config"',
            "Agent 2 harvests the live estate",
        ],
        fill=FILL_ACCENT,
    )

    c.box(80, 210, 300, 54, ["S1  Intent capture", "LLM structured extraction to WorkloadIntent"])
    c.box(
        1020, 210, 300, 54, ["S1b  Intent reconstruction", "recover intent from estate structure"]
    )
    c.box(
        1020,
        292,
        300,
        46,
        ["Per-field confidence", "below threshold: confirm with the user"],
        dashed=True,
    )

    c.box(
        470,
        300,
        460,
        54,
        ["S2  Knowledge graph query + constraint mask", "candidates ranked by the Recommender"],
        fill=FILL_ACCENT,
    )
    c.box(470, 386, 460, 46, ["S3  Candidate specification assembled"])
    c.box(
        470,
        466,
        460,
        54,
        [
            "S4  Advisor review (bounded iteration)",
            "grounded in L1 controls, never in the Recommender's output",
        ],
    )
    c.box(150, 466, 260, 54, ["Advisor findings", "implement suggestions in the spec"])
    c.box(
        980,
        466,
        320,
        54,
        ["Non-convergence", "report contested findings rather than", "manufacturing agreement"],
        dashed=True,
    )

    c.box(
        470,
        566,
        460,
        54,
        [
            "S5  Dependency graph of the specification",
            "multi-hop relational checks (defect class DF-7)",
        ],
        fill=FILL_ACCENT,
    )
    c.box(
        470,
        646,
        460,
        54,
        ["S6  Explanation", "reasoning subgraph + counterfactual, audience-relative"],
    )
    c.box(470, 726, 460, 46, ["S7  User gate — accept specification and dependency graph?"])
    c.box(80, 726, 300, 46, ["User inputs changes", "spec updated, return to S4"], dashed=True)

    c.box(
        470, 806, 460, 54, ["S8  Terraform plan (Agent 1)", "preview only; blast radius reported"]
    )
    c.box(470, 886, 460, 46, ["S9 Apply   ·   S10 Run record persisted to L3"])
    c.box(
        1000, 806, 320, 54, ["Post-apply drift check", "re-harvest, compare, feed L3"], dashed=True
    )

    c.arrow(230, 176, 230, 210)
    c.arrow(1170, 176, 1170, 210)
    c.arrow(1170, 264, 1170, 292)
    c.elbow(380, 237, 700, 300)
    c.arrow(1020, 327, 932, 327)
    c.arrow(700, 354, 700, 386)
    c.arrow(700, 432, 700, 466)
    c.arrow(470, 493, 412, 493, "revise")
    c.path([(280, 466), (280, 409), (468, 409)])
    c.arrow(930, 493, 978, 493, "iteration cap reached", lx=954, ly=474)
    c.arrow(700, 520, 700, 566, "approved")
    c.arrow(700, 620, 700, 646)
    c.arrow(700, 700, 700, 726)
    c.arrow(470, 749, 382, 749, "no")
    c.path([(230, 726), (230, 540), (448, 540), (448, 500), (468, 500)])
    c.arrow(700, 772, 700, 806, "yes")
    c.arrow(700, 860, 700, 886)
    c.arrow(930, 833, 998, 833)
    c.path(
        [(1320, 833), (1355, 833), (1355, 315), (1322, 315)],
        "confirmed intent feeds L3",
        lx=1240,
        ly=880,
    )

    c.text(
        40,
        962,
        "Invariant — the audience setting changes only how a result is rendered. The "
        "conclusion is identical for architect, auditor and learner, and this is tested rather "
        "than asserted.",
        size=12,
        anchor="start",
        fill=MUTED,
    )
    c.text(
        40,
        986,
        "Implemented today: S1b intent reconstruction with per-field calibration, the "
        "estate dependency graph, and the defect corpus. S2, S4 and S6 are Phase-II.",
        size=12,
        anchor="start",
    )
    return c


def write(name: str, canvas: Canvas) -> None:
    canvas.to_png(HERE / f"{name}.png")
    canvas.to_svg(HERE / f"{name}.svg")
    print(f"{name}.png + {name}.svg")


if __name__ == "__main__":
    write("AWS_Architecture", aws_architecture())
    write("System_Architecture", system_architecture())
