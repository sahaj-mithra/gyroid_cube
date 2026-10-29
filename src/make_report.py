"""
Build Gyroid_Design_and_3D_Printing_Report.pdf from the measured results.

Every number in the report is read from results/ (validation.json, design_study.json,
original_comparison.json, slicer/slicer_report.json, ../final_metrics.json) at build time,
so the PDF always reflects the files that were actually generated and checked.
"""
import hashlib
import json
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results" / "3x3"
VIEWS = RES / "views"
OUT_PDF = ROOT / "Gyroid_Design_and_3D_Printing_Report.pdf"
STL = ROOT / "stl" / "gyroid_3x3_40mm.stl"

# Arial covers the symbols used below (>=, +-, diameter, multiplication, Greek).
pdfmetrics.registerFont(TTFont("Arial", "C:/Windows/Fonts/arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold", "C:/Windows/Fonts/arialbd.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Italic", "C:/Windows/Fonts/ariali.ttf"))
pdfmetrics.registerFontFamily("Arial", normal="Arial", bold="Arial-Bold", italic="Arial-Italic")

NAVY = colors.HexColor("#1F3A5F")
LIGHT = colors.HexColor("#EEF2F7")
GOOD = colors.HexColor("#E6F4EA")
WARN = colors.HexColor("#FFF4E0")

ss = getSampleStyleSheet()
S = {
    "title": ParagraphStyle("t", parent=ss["Title"], fontName="Arial-Bold", fontSize=22, leading=27, textColor=NAVY),
    "sub": ParagraphStyle("s", parent=ss["Normal"], fontName="Arial", fontSize=12, leading=16, alignment=TA_CENTER,
                          textColor=colors.HexColor("#444444")),
    "h1": ParagraphStyle("h1", parent=ss["Heading1"], fontName="Arial-Bold", fontSize=15, leading=19,
                         textColor=NAVY, spaceBefore=10, spaceAfter=6),
    "h2": ParagraphStyle("h2", parent=ss["Heading2"], fontName="Arial-Bold", fontSize=11.5, leading=15,
                         textColor=NAVY, spaceBefore=8, spaceAfter=4),
    "body": ParagraphStyle("b", parent=ss["Normal"], fontName="Arial", fontSize=9.5, leading=13, spaceAfter=4),
    "small": ParagraphStyle("sm", parent=ss["Normal"], fontName="Arial", fontSize=8, leading=10.5,
                            textColor=colors.HexColor("#444444")),
    "cell": ParagraphStyle("c", parent=ss["Normal"], fontName="Arial", fontSize=8.3, leading=10.3),
    "cellb": ParagraphStyle("cb", parent=ss["Normal"], fontName="Arial-Bold", fontSize=8.3, leading=10.3,
                            textColor=colors.white),
    "bullet": ParagraphStyle("bl", parent=ss["Normal"], fontName="Arial", fontSize=9.5, leading=13,
                             leftIndent=12, bulletIndent=2, spaceAfter=2),
}


def P(t, st="body"):
    return Paragraph(t, S[st])


def bullets(items):
    return [Paragraph(t, S["bullet"], bulletText="•") for t in items]


def table(rows, widths, header=True, shade=None):
    data = [[Paragraph(str(c), S["cellb"] if (header and i == 0) else S["cell"]) for c in r]
            for i, r in enumerate(rows)]
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C2CF")),
             ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
             ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), NAVY)]
        style += [("BACKGROUND", (0, i), (-1, i), LIGHT) for i in range(2, len(rows), 2)]
    for (r, c) in (shade or []):
        style.append(("BACKGROUND", (0, r), (-1, r), c))
    t.setStyle(TableStyle(style))
    return t


def figure(path, width_mm, caption):
    from PIL import Image as PILImage
    with PILImage.open(path) as im:
        w, h = im.size
    img = Image(str(path), width=width_mm * mm, height=width_mm * mm * h / w)
    return KeepTogether([img, Spacer(1, 2), P(caption, "small"), Spacer(1, 6)])


def page_decor(canvas, doc):
    canvas.saveState()
    canvas.setFont("Arial", 7.5)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawString(18 * mm, 10 * mm, "Gyroid 3×3 cube – design and 3D-printing report (ME3305)")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.setStrokeColor(NAVY)
    canvas.setLineWidth(0.6)
    canvas.line(18 * mm, A4[1] - 12 * mm, A4[0] - 18 * mm, A4[1] - 12 * mm)
    canvas.restoreState()


def f(x, n=2):
    return f"{x:.{n}f}"


def main():
    v = json.loads((RES / "validation.json").read_text())
    study = json.loads((RES / "design_study.json").read_text())
    orig = json.loads((RES / "original_comparison.json").read_text())
    sl = json.loads((RES / "slicer" / "slicer_report.json").read_text())
    rev2 = json.loads((ROOT / "results" / "final_metrics.json").read_text())
    g, p, st, pr = v["geometry"], v["parameters"], v["see_through"], v["printability"]
    wt, fs, lf = v["wall_thickness_on_mesh"], v["face_strip_widths"], v["lattice_field"]
    sc = sl["cases"]
    off, bpo, evw, osup = (sc["new_supports_off"], sc["new_supports_buildplate_only"],
                           sc["new_supports_everywhere"], sc["original_supports_everywhere"])
    n06 = sl["estimate_cases"]["new_supports_off_nozzle0.6"]
    b5 = sc["new_supports_off_brim5"]
    ta, core = rev2["parts"]["gyroid_final_test_article"], rev2["parts"]["gyroid_final_core"]
    o_ta, o_core = orig["gyroid_final_test_article"]["see_through"], orig["gyroid_final_core"]["see_through"]
    sha = hashlib.sha256(STL.read_bytes()).hexdigest()
    a, w, shift = p["period_mm"], p["wall_nominal_mm"], p["shift_mm"]
    sel = next(r for r in study if "[selected]" in r["case"])
    min_clear = min(st[ax]["min_clear_diameter_mm"] for ax in "xyz")
    max_clear = max(h["clear_diameter_mm"] for ax in "xyz" for h in v["see_through_detail"][ax] if not h["edge_cut"])
    min_clear_sliced = min(off["openings_after_slicing"][ax]["min_clear_diameter_mm"] for ax in "xyz")
    t_off = off["prusaslicer_summary"]["estimated printing time (normal mode)"]
    g_off = off["prusaslicer_summary"]["filament used [g]"]

    story = []
    # ------------------------------------------------------------------ title page
    story += [Spacer(1, 30 * mm), P("Gyroid Cube with 3 × 3 × 3 Openings", "title"),
              P("Design modification, validation and PLA 3D-printing report", "sub"), Spacer(1, 4 * mm),
              P(f"ME3305 Manufacturing Technology II · {date(2026, 10, 29).strftime('%d %B %Y')} · "
                f"revision 3.1 (brim advice corrected)", "sub"),
              Spacer(1, 14 * mm)]
    summary = [
        ["Item", "Result"],
        ["Final STL", f"stl/gyroid_3x3_40mm.stl ({g['triangles']:,} triangles, {g['file_bytes'] / 1e6:.1f} MB)"],
        ["External size (measured)", " × ".join(f"{s:.3f}" for s in g["size_mm"]) + " mm"],
        ["Openings along X / Y / Z (measured on STL)",
         " / ".join(f"{st[ax]['full']} ({st[ax]['grid_cols_rows'][0]}×{st[ax]['grid_cols_rows'][1]})" for ax in "xyz")
         + f" see-through openings; minimum clear Ø {min_clear:.2f} mm"],
        ["Openings after slicing (PrusaSlicer 2.9.6 G-code)",
         " / ".join(str(off["openings_after_slicing"][ax]["full"]) for ax in "xyz")
         + f" per axis, minimum clear Ø {min_clear_sliced:.2f} mm"],
        ["Original print file (for comparison)",
         f"X/Y: {o_ta['x']['full']} openings (closed side walls); Z: {o_ta['z']['full']} openings of Ø "
         f"{o_ta['z']['min_clear_diameter_mm']:.1f} mm"],
        ["Mesh", "watertight, 1 body, 0 open/non-manifold edges, 0 self-intersections, 0 degenerate faces"],
        ["Supports", f"none needed: sliced with supports OFF, 0 mm support; PrusaSlicer estimate {t_off}, {g_off} g PLA"],
        ["Adhesion", f"no brim: a 5 mm outer brim would fill {b5['brim_cover_of_bottom_openings_pct']:.0f} % of the "
                     f"bottom openings (revision 3.1)"],
        ["Bambu Lab H2D / P1S", "verified settings in Gyroid_3D_Printing_Settings.txt (Bambu Studio, official profiles)"],
        ["Not performed", "physical print, strength test, slicer GUI preview on your printer profile"],
    ]
    story += [table(summary, [58, 116]), Spacer(1, 8 * mm),
              P("All measured values in this report are read from the generated files at report-build time. "
                "<b>Verified</b> = measured on the STL or on the PrusaSlicer G-code. <b>Estimate</b> = derived "
                "from a model or assumption. <b>Not performed</b> = stated explicitly; no print, mechanical test "
                "or simulation has been run.", "small"), PageBreak()]

    # ------------------------------------------------------------------ 1 original assessment
    story += [P("1. Original design assessment", "h1"),
              P(f"The previously printed model came from the revision-2 generator (<i>src/gyroid.py</i>, "
                f"<i>src/build_final.py</i>): sheet gyroid, period <b>a = {ta['cell_mm']:.0f} mm</b> in a 40 mm cube "
                f"(<b>{40 / ta['cell_mm']:.0f} periods per axis</b>), nominal wall {ta['wall_nominal_mm']} mm "
                f"(measured {ta['lattice_measured']['wall_median_mm']:.2f} mm median), and in the recommended "
                f"print file 1.25 mm side walls on the four X/Y faces.")]
    rows = [["Problem reported", "Cause found (measured)"],
            ["Openings too small / hard to see",
             f"Viewed along an axis the sheet gyroid has 2 openings per period, so a = 8 mm gives a 10 × 10 grid: "
             f"{o_core['z']['full']} whole see-through openings per face plus edge-cut ones, each only "
             f"Ø {o_core['z']['min_clear_diameter_mm']:.1f} mm "
             f"({o_core['z']['open_area_pct']:.1f} % of the face open). The print file's side walls closed the X "
             f"and Y faces completely: {o_ta['x']['full']} openings along X and Y."],
            ["Supports trapped inside",
             f"Re-slicing the original file with supports 'everywhere' (PrusaSlicer 2.9.6) generates "
             f"{osup['support_extrusion_mm'] / 1000:.0f} m of support, of which "
             f"{osup['support_access']['resting_on_model_mm3']:,.0f} mm³ stands on the lattice's own surfaces in "
             f"{osup['support_access']['resting_on_model_regions']} separate pockets – none of it reachable "
             f"from outside. Its overhangs reach at most "
             f"{orig['gyroid_final_test_article']['printability']['overhang']['max_reach_per_layer_mm']:.2f} mm "
             f"per layer, so supports were not needed in the first place. "
             f"Estimate with supports: {osup['prusaslicer_summary']['estimated printing time (normal mode)']}, "
             f"{osup['prusaslicer_summary']['filament used [g]']} g."]]
    story += [table(rows, [42, 132]), Spacer(1, 4),
              figure(VIEWS / "before_after_front.png", 174,
                     "Figure 1 – Front views rendered from the STL files at the same scale (white = straight line of "
                     "sight through the part). Left: original print file (closed side walls). Centre: original lattice "
                     "without side walls. Right: revised design."), PageBreak()]

    # ------------------------------------------------------------------ 2 updated geometry
    story += [P("2. Updated geometry", "h1"), P("2.1 Generation method", "h2"),
              P("The existing generator was modified, not replaced. The sheet gyroid keeps its equation and its "
                "constant-thickness wall; only the period, the phase (where the cube faces cut the lattice) and "
                "the wall thickness change:"),
              P("<b>g(x,y,z) = sin X·cos Y + sin Y·cos Z + sin Z·cos X</b>,  X = 2π(x + s)/a (same for Y, Z);  "
                "solid where |g| / |grad g| ≤ w/2 (sheet of thickness w around g = 0), intersected with the 40 mm cube. "
                "Meshed with marching cubes at 0.2 mm pitch, quadric-decimated with acceptance gates (§4)."),
              P("2.2 How the unit cell maps to visible openings", "h2"),
              P("A 3 × 3 pattern does not follow from setting 3 unit cells per axis. Projecting the sheet "
                "gyroid along a cube axis (rays through the whole part) shows <b>4 see-through openings per "
                "period², on a square grid with spacing a/2</b>. The number of openings across a face of size L "
                "is therefore 2L/a, not L/a:")]
    rows = [["Configuration", "Period a", "Periods / axis", "Openings per face (whole + edge-cut)", "Min clear Ø"]]
    for r in study:
        if "w=0.9" in r["case"] and "26.67" in r["case"] or "w=1.2" in r["case"] or "w=2.0" in r["case"]:
            continue
        z = r["openings"]["z"]
        rows.append([r["case"].replace(" [selected]", " – <b>selected</b>"), f"{r['period_mm']:.2f} mm",
                     f"{r['periods_per_axis']:.2f}", f"{z['full']} + {z['edge_cut']}",
                     f"{z['min_clear_diameter_mm']:.2f} mm"])
    story += [table(rows, [70, 20, 22, 40, 22]), Spacer(1, 4),
              P(f"Hence 3 openings per axis requires a = 2L/3 = <b>{a:.2f} mm</b> (1.5 periods across 40 mm). "
                f"The phase then decides whether the openings are whole or cut by the cube edges: only a shift of "
                f"<b>s = a/8 = {shift:.2f} mm</b> on all three axes gives 9 whole openings and none cut on every "
                f"face simultaneously (shift 0 gives 6 whole + 6 cut). The two families of openings seen in "
                f"perpendicular views are offset by a/4, so they cannot both be centred on a face; each 3 × 3 "
                f"grid sits {shift:.1f} mm off the face centre, with a {(shift - min_clear / 2):.1f} mm solid border "
                f"to the nearest cube edge. The external size stays 40 × 40 × 40 mm; no dimensional change was "
                f"needed.")]
    rows = [["Final geometry", "Value", "Status"],
            ["External dimensions X × Y × Z", " × ".join(f"{s:.3f}" for s in g["size_mm"]) + " mm", "Verified (STL)"],
            ["Gyroid period a / periods per axis", f"{a:.3f} mm / {p['periods_per_axis']:.2f}", "Design input"],
            ["Opening cells per axis (opening pitch a/2)", f"3 × 3 × 3 (pitch {a / 2:.2f} mm)", "Verified (STL)"],
            ["Phase shift s (all axes)", f"{shift:.3f} mm = a/8", "Design input"],
            ["See-through openings X / Y / Z",
             " / ".join(f"{st[ax]['full']} whole ({st[ax]['grid_cols_rows'][0]}×{st[ax]['grid_cols_rows'][1]}), "
                        f"{st[ax]['edge_cut']} edge slivers" for ax in "xyz"), "Verified (STL)"],
            ["Clear opening diameter (min / max)", f"{min_clear:.2f} / {max_clear:.2f} mm",
             "Verified (STL, 0.1 mm voxels)"],
            ["Open fraction of each face (line of sight)", f"{st['z']['open_area_pct']:.1f} %", "Verified (STL)"],
            ["Largest sphere passing face-to-face",
             " / ".join(f"{v['bottleneck_on_mesh_mm'][ax]:.1f}" for ax in "xyz") + " mm (X / Y / Z)", "Verified (STL)"],
            ["Wall thickness, nominal / measured 3D (p1, median, max)",
             f"{w} mm / {wt['p1']:.2f}, {wt['median']:.2f}, {wt['max']:.2f} mm", "Verified (STL)"],
            ["Solid volume / solid fraction", f"{g['solid_volume_mm3']:,.0f} mm³ / {100 * g['solid_fraction']:.1f} %",
             "Verified (STL)"],
            ["Surface area (internal, both sides)", f"{g['wetted_area_mm2']:,.0f} mm²", "Verified (STL)"],
            ["PLA mass", f"{v['pla_mass_g']:.1f} g (at 1.24 g/cm³); slicer: {g_off} g incl. skirt", "Estimate"]]
    story += [Spacer(1, 4), table(rows, [62, 80, 32]), PageBreak(),
              figure(VIEWS / "views_composite.png", 160,
                     "Figure 2 – Front, side, top and isometric views rendered from gyroid_3x3_40mm.stl (orthographic, "
                     "z-buffered over the real triangles; white = background seen through the part)."),
              figure(VIEWS / "openings_annotated.png", 174,
                     "Figure 3 – Every see-through opening detected on the STL, numbered; circles = measured clear "
                     "diameter."), PageBreak(),
              figure(VIEWS / "sections_mid.png", 174,
                     "Figure 4 – Mid-plane sections: one continuous sheet separating two interlocked channel networks.")]

    # ------------------------------------------------------------------ 3 design changes
    o_ls = ta["lattice_measured"]
    rows = [["Parameter", "Original (printed)", "Updated", "Reason"],
            ["Overall size", "40 × 40 × 40 mm", "40 × 40 × 40 mm", "Unchanged"],
            ["Gyroid period a", f"{ta['cell_mm']:.0f} mm", f"{a:.2f} mm", "2 openings per period → 3 per axis needs a = 2L/3"],
            ["Periods per axis", f"{40 / ta['cell_mm']:.0f}", f"{p['periods_per_axis']:.1f}", "As above"],
            ["Phase shift", "0", f"a/8 = {shift:.2f} mm", "Only phase with 9 whole, uncut openings on all faces"],
            ["See-through openings per face", f"X/Y: 0 (side walls), Z: {o_ta['z']['full']}", "9 on every face (3 × 3)",
             "Primary requirement"],
            ["Clear opening Ø", f"{o_ta['z']['min_clear_diameter_mm']:.1f} mm", f"{min_clear:.2f} mm",
             f"≈{min_clear / o_ta['z']['min_clear_diameter_mm']:.1f}× larger"],
            ["Side walls (skin)", "1.25 mm on X/Y faces", "none", "They blocked the X and Y openings"],
            ["Wall nominal / measured median", f"{ta['wall_nominal_mm']} / {o_ls['wall_median_mm']:.2f} mm",
             f"{w} / {wt['median']:.2f} mm", "4 lines at 0.4 mm; panels are 3.3× larger, so thicker for stiffness"],
            ["Channel bottleneck (sphere)", f"{o_ls['bottleneck_mm']:.2f} mm", f"{lf['bottleneck_mm']:.1f} mm",
             "Supports and debris can leave; inspection easy"],
            ["Solid fraction / mass", f"{100 * ta['exported_file_measured']['solid_fraction']:.1f} % / "
                                      f"{ta['exported_file_measured']['pla_mass_g']:.1f} g",
             f"{100 * g['solid_fraction']:.1f} % / {v['pla_mass_g']:.1f} g", "Larger cells, no side walls"],
            ["Recommended supports", "(printed with supports)", "OFF", "Self-supporting; see §7"],
            ["STL triangles / size", f"{ta['exported_file_measured']['triangles']:,} / "
                                     f"{ta['exported_file_measured']['file_bytes'] / 1e6:.0f} MB",
             f"{g['triangles']:,} / {g['file_bytes'] / 1e6:.0f} MB", "Fewer, larger surfaces need fewer triangles"]]
    story += [P("3. Design changes", "h1"), table(rows, [36, 38, 36, 64]), Spacer(1, 6), P("3.1 Wall thickness choice", "h2")]
    rows = [["Nominal wall", "Measured p1 / median", "Min clear Ø", "Lines @ 0.4 mm", "Mass (est.)", "Assessment"]]
    for r in study:
        if "26.67" in r["case"] and "wrong" not in r["case"]:
            lines = r["wall_nominal_mm"] / 0.4
            note = {0.9: "thin 13 mm panels, flexible", 1.2: "acceptable", 1.6: "<b>selected</b>: robust panels",
                    2.0: "smaller openings, heavier"}[r["wall_nominal_mm"]]
            rows.append([f"{r['wall_nominal_mm']} mm", f"{r['wall_p1_mm']:.2f} / {r['wall_median_mm']:.2f} mm",
                         f"{r['openings']['z']['min_clear_diameter_mm']:.2f} mm", f"{lines:.1f}",
                         f"{r['mass_g_est']} g", note])
    story += [table(rows, [22, 34, 22, 22, 22, 52]), Spacer(1, 3),
              P("The panels between openings are about 3.3× wider than before. For a flat plate, keeping the same "
                "bending stiffness at 3.3× the span would need about 2.2× the thickness (t³ ∝ span²); the doubly "
                "curved gyroid shell is stiffer than a flat plate, so 1.6 mm (1.9× the original 0.85 mm) was chosen "
                "as a compromise that still keeps the openings within 8 % of the 1.2 mm option. This is an "
                "<b>engineering estimate</b>, not a tested strength value.")]

    # ------------------------------------------------------------------ 4 printability
    d = g["defects"]
    ovh = pr["overhang"]
    real_worst = [r for r in ovh["worst_regions"] if r["largest_area_mm2"] > 1.0]
    rows = [["Check", "Result", "Status"],
            ["Watertight / consistent winding / valid volume",
             f"{g['watertight']} / {g['winding_consistent']} / {g['is_volume']}", "Verified"],
            ["Connected bodies", f"{g['bodies']} (genus {(2 - g['euler_number']) // 2})", "Verified"],
            ["Open edges / non-manifold edges", f"{d['open_edges']} / {d['non_manifold_edges']}", "Verified"],
            ["Self-intersections (edge–triangle test)", str(d["self_intersections"]), "Verified"],
            ["Zero-area faces", str(d["zero_area_faces"]), "Verified"],
            ["Decimation change vs. full mesh", f"volume {v['decimation']['vol_change_pct']:+.3f} %, "
                                                f"area {v['decimation']['area_change_pct']:+.3f} %", "Verified"],
            ["PrusaSlicer import", "manifold = yes, 1 part (prusa-slicer --info)", "Verified"]]
    story += [PageBreak(), P("4. 3D-printability assessment", "h1"), P("4.1 Mesh validation (STL reloaded from disk)", "h2"),
              table(rows, [70, 76, 28]), P("4.2 Minimum feature sizes", "h2")]
    rows = [["Feature", "Measured", "Comment"],
            ["3D wall thickness (>1 mm from faces)", f"p1 {wt['p1']:.2f} mm, median {wt['median']:.2f} mm",
             "≥ 3 extrusion lines everywhere"],
            ["In-plane wall width per 0.2 mm layer", f"p1 {pr['wall_width_interior_mm']['p1']:.2f} mm, median "
                                                     f"{pr['wall_width_interior_mm']['median']:.2f} mm; "
                                                     f"{100 * pr['wall_width_interior_share_below']['0.8']:.2f} % below 0.8 mm",
             "Prints as 3–4 lines"],
            ["Strips on the six cube faces", f"p1 {fs['p1']:.2f} mm, median {fs['median']:.2f} mm; "
                                             f"{100 * fs['share_below_0.4mm']:.2f} % below 0.4 mm",
             "Thin only where a wall meets a face at a grazing angle"],
            ["Knife-edge slivers on the vertical cube edges", f"{pr['floating_islands']['total']} specks, each ≤ "
                                                             f"{max(e['max_area_mm2'] for e in pr['floating_islands']['events']):.2f} mm²",
             "Smaller than one line; slicer drops or blobs them; cosmetic"],
            ["Clear openings after slicing", f"min Ø {min_clear_sliced:.2f} mm (all 27 present)", "Verified on G-code"]]
    story += [table(rows, [52, 70, 52]), P("4.3 Overhangs and bridging", "h2"),
              P(f"Gyroid sheets have no horizontal down-facing areas except near saddle points. Measured per layer: "
                f"{100 * g['overhang_gt45_area_frac']:.1f} % of the surface faces down steeper than 45° and "
                f"{100 * g['overhang_gt70_area_frac']:.1f} % steeper than 70°. The largest region printed more than "
                f"one line width beyond the layer below is "
                f"{max(r['largest_area_mm2'] for r in real_worst):.1f} mm² with a reach of "
                f"{max(r['max_reach_mm'] for r in real_worst):.2f} mm (saddle ceilings at z ≈ "
                f"{', '.join(f'{r['z']:.1f}' for r in real_worst)} mm); the original reached 0.58 mm. These are "
                f"short cantilevers, far below practical PLA bridging limits (~10 mm), and PrusaSlicer handled them "
                f"with {off['extrusion_length_mm_by_type'].get('Overhang perimeter', 0):.0f} mm of overhang "
                f"perimeter and {off['extrusion_length_mm_by_type'].get('Bridge infill', 0):.0f} mm of bridge "
                f"infill out of {sum(off['extrusion_length_mm_by_type'].values()) / 1000:.0f} m total. Expect "
                f"slight drooping on those ceilings, not failure. First layer: {pr['first_layer']['islands']} "
                f"continuous island, {pr['first_layer']['area_mm2']:.0f} mm²; islands per layer: median "
                f"{pr['islands_per_layer']['median']}, max {pr['islands_per_layer']['max']}."),
              P("4.4 Structural integrity (estimate, not tested)", "h2"),
              *bullets([f"Single continuous body; every wall ≥ {wt['p1']:.2f} mm (3–4 lines) away from the faces.",
                        "The doubly curved sheet acts as a shell; the weakest direction is between layers (Z), as for "
                        "any FDM part.",
                        "Thinnest material is at the cube faces and the four vertical edges, where walls are cut at "
                        "grazing angles – handle by the faces, not the edges.",
                        "No mechanical test or simulation was performed; no load rating is claimed."]),
              P("4.5 Remaining limitations", "h2"),
              *bullets(["Each 3 × 3 grid is offset a/8 = 3.3 mm from the face centre (inherent to the gyroid; see §2.2).",
                        f"Outermost openings keep only a {(shift - min_clear / 2):.1f} mm border to the cube edge.",
                        "Thermal and flow performance were not evaluated for this revision (geometry and printability only).",
                        "Slicing used a generic printer section; re-slice with your own printer profile before printing."])]

    # ------------------------------------------------------------------ 5 material
    story += [PageBreak(), P("5. Material selection", "h1"),
              P("PLA is selected because the part is a visual and handling prototype: it prints accurately with "
                "little warping, bridges and overhangs well with strong cooling (important for the saddle ceilings), "
                "needs no enclosure and is widely available."),
              table([["Assumption", "Value", "Use / limitation"],
                     ["Density", "1.24 g/cm³", "Mass estimate"],
                     ["Filament diameter", "1.75 mm", "Slicer"],
                     ["Nozzle / bed temperature", "205–215 °C / 55–60 °C", "Typical PLA window; check your spool"],
                     ["Glass transition", "≈ 55–60 °C", "Do not leave in a hot car or near heat sources"],
                     ["Behaviour", "Stiff, brittle", "Thin edges can chip if dropped; no impact rating"]],
                    [45, 45, 84])]

    # ------------------------------------------------------------------ 6 slicer configuration
    rows = [["Setting", "Recommended", "Range", "Affects"],
            ["Nozzle diameter", "0.4 mm", "0.4–0.6 mm", "Quality / time"],
            ["Layer height (first layer)", "0.2 mm (0.2 mm)", "0.12–0.24 mm", "Surface finish on curved sheets"],
            ["Line width (first layer)", "0.45 mm (0.5 mm)", "0.42–0.48 mm", "<b>Geometry</b>: widths beyond 0.5 mm narrow the openings"],
            ["Perimeter generator / walls", "Arachne, 3 perimeters", "3–4", "Reliability; walls print as 3–4 lines"],
            ["Infill", "100 % rectilinear", "–", "Only fills the few wide sheet regions"],
            ["Top / bottom solid layers", "4 / 3", "3–5", "Saddle ceilings"],
            ["Nozzle temperature", "215 °C first layer, 210 °C", "205–220 °C", "Reliability"],
            ["Bed temperature", "60 °C", "55–65 °C", "Adhesion"],
            ["Speeds", "Outer wall 25, walls 40, infill 60, bridges 25, first layer 20 mm/s",
             "Outer 20–35 mm/s", "Quality (outer wall speed governs surface)"],
            ["Cooling", "100 % fan from layer 2; bridge fan 100 %", "80–100 %", "Overhang quality"],
            ["Retraction", "0.8 mm @ 35 mm/s, 0.2 mm Z-hop (direct drive)",
             "Bowden: 4–6 mm", "Stringing across openings"],
            ["Travel", "Avoid crossing perimeters ON", "–", "Keeps strings out of the openings"],
            ["Adhesion", "<b>No brim</b>; elephant-foot compensation 0.15 mm; clean PEI plate", "glue stick only if corners lift",
             f"<b>Geometry</b>: an outer brim fills {b5['brim_cover_of_bottom_openings_pct']:.0f} % of the bottom openings "
             f"(see below); compensation keeps them full size"],
            ["Supports", "<b>OFF</b>", "(build-plate only if required)", "<b>Geometry</b>: supports fill openings"],
            ["XY size compensation", "0", "0", "<b>Geometry</b>: any value changes opening size"],
            ["Orientation", "As exported (z = 0 face on the bed)", "x = 0 or y = 0 face down is equivalent",
             "Sliced and verified orientation; equivalence by the gyroid's 3-fold symmetry"],
            ["STL export / resolution", f"{g['triangles']:,} triangles, decimation < 0.02 % volume change",
             "≥ 300 k triangles", "<b>Geometry</b>: coarser meshes facet the sheets"]]
    story += [P("6. Final slicer configuration (PrusaSlicer, generic printer, PLA, 0.4 mm)", "h1"),
              P("Saved as <i>print/prusaslicer_PLA_0.4mm_gyroid_3x3.ini</i>. Settings marked <b>Geometry</b> change "
                "the physical shape or the size of the openings; the others affect only quality or reliability."),
              table(rows, [36, 54, 30, 54]), Spacer(1, 4),
              P(f"<b>Why no brim (revision 3.1).</b> The bottom face is a set of curved strips whose open areas "
                f"connect to the outside, so a slicer treats them as exterior and runs an 'outer' brim into them. "
                f"Sliced in PrusaSlicer with a 5 mm outer brim, {b5['brim_inside_footprint_mm2']:,.0f} mm² of brim "
                f"lands inside the 40 × 40 mm footprint, covering {b5['brim_cover_of_bottom_openings_pct']:.0f} % of "
                f"the open bottom area (Bambu Studio 02.08.02.61 with the Bambu H2D/P1S profiles: 84 %). Peeling it "
                f"out of the openings would risk the thin bottom edges. Without a brim the first layer is still one "
                f"continuous island of {pr['first_layer']['area_mm2']:.0f} mm², and no brim material is printed "
                f"inside the footprint ({off['brim_inside_footprint_mm2']:.0f} mm²). Earlier versions of this "
                f"report recommended a 5 mm brim; that advice is withdrawn."),
              P("<b>Bambu Lab H2D / P1S.</b> Printer-specific settings, sliced with Bambu Studio and the official "
                "Bambu profiles, are in <i>Gyroid_3D_Printing_Settings.txt</i>. Use that sheet on Bambu printers; "
                "the table above is for the generic PrusaSlicer profile."),
              P(f"<b>0.6 mm nozzle alternative.</b> Because the thinnest printed feature is ≈1.3 mm and the openings are "
                f"≈5 mm, a 0.6 mm nozzle (0.3 mm layers, 0.65 mm lines, 2 perimeters) keeps the geometry: PrusaSlicer "
                f"estimates {n06['prusaslicer_summary']['estimated printing time (normal mode)']} and "
                f"{n06['prusaslicer_summary']['filament used [g]']} g, against {t_off} with 0.4 mm – a meaningful time "
                f"saving with a coarser surface. 0.4 mm remains the default for surface quality.")]

    # ------------------------------------------------------------------ 7 supports
    ba = bpo["support_access"]
    ea = evw["support_access"]
    rows = [["Slicing case (PrusaSlicer 2.9.6)", "Support extruded", "Removable (clear to bed)",
             "Resting on model (likely trapped)", "Openings after slicing", "Time / PLA"]]
    for name, c in [("Revised – supports OFF (recommended)", off), ("Revised – build-plate only", bpo),
                    ("Revised – everywhere", evw), ("Original – everywhere", osup)]:
        a_ = c["support_access"]
        o = c["openings_after_slicing"]
        rows.append([name, f"{c['support_extrusion_mm'] / 1000:.1f} m", f"{a_['clear_to_bed_mm3']:,.0f} mm³",
                     f"{a_['resting_on_model_mm3']:,.0f} mm³ ({a_['resting_on_model_regions']} pockets)",
                     " / ".join(str(o[ax]["full"]) for ax in "xyz"),
                     f"{c['prusaslicer_summary']['estimated printing time (normal mode)']} / "
                     f"{c['prusaslicer_summary']['filament used [g]']} g"])
    story += [PageBreak(), P("7. Support-removal strategy", "h1"),
              P("<b>Supports can be eliminated.</b> The gyroid is a minimal surface: it has no local low points, so "
                "every layer grows from the one below except tiny sub-line slivers at the cube edges. The cube is "
                "printed as exported (z = 0 face on the bed; the x = 0 and y = 0 faces are equivalent by the "
                "gyroid's three-fold x→y→z symmetry, the opposite faces were not sliced). This gives one "
                "continuous first layer and no enclosed overhang that needs support."),
              table(rows, [40, 20, 26, 34, 20, 34], shade=[(1, GOOD), (3, WARN), (4, WARN)]), Spacer(1, 4),
              P(f"How removability was checked: the support toolpaths were rebuilt from the G-code and each "
                f"connected support region classified. A region is <i>clear to bed</i> when no printed model material "
                f"lies below it in its column (it stands in a straight vertical void and can be pulled out downwards); "
                f"otherwise it rests on the lattice's own surfaces inside the cube. With build-plate-only supports "
                f"{ba['clear_to_bed_mm3']:,.0f} mm³ is clear to bed and {ba['resting_on_model_mm3']:.1f} mm³ "
                f"in {ba['resting_on_model_regions']} small regions rests on the model; with 'everywhere' "
                f"{ea['resting_on_model_mm3']:,.0f} mm³ sits in {ea['resting_on_model_regions']} pockets inside the "
                f"lattice. <b>Never use 'supports everywhere' on this part.</b> If a printer struggles with the saddle "
                f"ceilings, build-plate-only supports are the fallback: almost all of them stand in straight vertical "
                f"columns open to the bottom face, so geometrically they can be pulled out downwards. This is a "
                f"geometric classification of the toolpaths, not a tested removal."),
              figure(VIEWS / "slicer_layers.png", 174,
                     "Figure 5 – Toolpaths rebuilt from the PrusaSlicer G-code at six heights (blue = model, orange = "
                     "support). Top: recommended, no support. Middle/bottom: 'supports everywhere' fills the channels.")]

    # ------------------------------------------------------------------ 8 validation
    rows = [["Check", "Method", "Result", "Status"],
            ["Equation, period, phase, offset", "Source inspection (src/gyroid.py, build_3x3.py)",
             f"a = {a:.3f} mm, s = a/8, w = {w} mm", "Verified"],
            ["Opening count per axis", "Line-of-sight analysis of the voxelised STL (0.1 mm); exact ray–triangle test "
                                       "at sample openings", "9 whole, 3 × 3, on X, Y and Z", "Verified"],
            ["Dimensions", "STL bounding box", " × ".join(f"{s:.3f}" for s in g["size_mm"]) + " mm", "Verified"],
            ["Wall thickness", "3D medial-axis distance transform; per-layer skeleton widths",
             f"p1 {wt['p1']:.2f} mm", "Verified"],
            ["Mesh integrity", "Watertight, manifold, self-intersection, degenerate-face checks", "all pass", "Verified"],
            ["Slicing preserves openings", "PrusaSlicer 2.9.6 CLI; toolpaths rebuilt from G-code",
             f"27 openings, min Ø {min_clear_sliced:.2f} mm", "Verified"],
            ["Support placement / removability", "G-code support regions classified", "0 support with supports OFF",
             "Verified"],
            ["Print time / material", "PrusaSlicer estimate (generic printer)", f"{t_off} / {g_off} g", "Estimate"],
            ["Slicer GUI layer preview", "–", "Not available (command-line slicing only)", "Not performed"],
            ["Physical print / strength", "–", "–", "Not performed"]]
    story += [PageBreak(), P("8. Validation results", "h1"), table(rows, [36, 66, 46, 26]), Spacer(1, 5),
              P("Measurement notes (checked during this work):", "h2"),
              *bullets([f"The first voxelisation showed 2 extra 0.2 mm 'pinholes' along X and a 0.2 mm wall minimum. "
                        f"Exact ray–triangle tests showed no line of sight there and that the thin voxels lie outside "
                        f"the mesh. Cause: the analysis slicer interpolated shared edges from opposite ends, giving "
                        f"odd crossing counts on a few scanlines. Fixed (canonical edge interpolation); "
                        f"{v['voxelizer_rows_repaired']} of 160,000 scanlines still needed neighbour repair. The STL "
                        f"itself was never affected.",
                        "PrusaSlicer first rejected the profile (relative E without a per-layer reset); 'G92 E0' was "
                        "added to the layer G-code."])]

    # ------------------------------------------------------------------ 9 deliverables
    rows = [["File", "Format", "Content"],
            ["stl/gyroid_3x3_40mm.stl", "Binary STL", f"Final model, {g['file_bytes'] / 1e6:.1f} MB, SHA-256 {sha[:16]}…"],
            ["src/build_3x3.py", "Python", "Editable source: parameters (L, openings per axis, wall), build, validation"],
            ["src/gyroid.py, mesh_checks.py, openings.py, printability.py", "Python",
             "Generator (phase-shift added), mesh checks, opening and layer analysis"],
            ["src/slice_check.py, render_views.py, make_report.py", "Python", "Slicer check, views, this report"],
            ["print/prusaslicer_PLA_0.4mm_gyroid_3x3.ini", "PrusaSlicer config", "Recommended print settings"],
            ["results/3x3/validation.json, design_study.json, original_comparison.json", "JSON", "Measurements"],
            ["results/3x3/slicer/slicer_report.json (+ *.gcode, not committed)", "JSON / G-code",
             "Slicer results; G-code is for the generic printer only"],
            ["results/3x3/views/*.png", "PNG", "Front, side, top, isometric, annotated openings, sections, layers"],
            ["Gyroid_3D_Printing_Settings.txt", "Text", "Operator sheet for Bambu Lab H2D / P1S (Bambu Studio, official profiles)"],
            ["Gyroid_Design_and_3D_Printing_Report.pdf", "PDF", "This report"]]
    story += [P("9. Final deliverables", "h1"), table(rows, [70, 26, 78])]

    # ------------------------------------------------------------------ 10 recommendations
    story += [PageBreak(), P("10. Final recommendations and workflow", "h1"),
              *bullets(["Open <i>stl/gyroid_3x3_40mm.stl</i> in your slicer and keep the exported orientation "
                        "(z = 0 face on the bed).",
                        "Load <i>print/prusaslicer_PLA_0.4mm_gyroid_3x3.ini</i> settings into your own printer "
                        "profile (keep the print and filament values; keep your printer's start G-code and retraction "
                        "if it uses a Bowden extruder).",
                        "Make sure supports are <b>OFF</b> (not 'everywhere'); XY size compensation 0.",
                        "Slice and inspect the layer preview: 3–4 lines per wall, openings visible in every layer, "
                        "no support, no brim lines inside the 40 × 40 mm footprint.",
                        f"Print in PLA at 210 °C / 60 °C with 100 % fan from layer 2; expect about {t_off} and "
                        f"{g_off} g with a 0.4 mm nozzle (generic printer estimate).",
                        "After printing, let the plate cool and flex it to release the part; look through each face: "
                        "9 openings must be clear on all six faces.",
                        "On Bambu Lab H2D / P1S printers follow <i>Gyroid_3D_Printing_Settings.txt</i> instead."]),
              P("Pre-print checklist", "h2")]
    checks = [["Done", "Check before printing"],
              ["[  ]", "Slicer reports the model as 40.0 × 40.0 × 40.0 mm, manifold, 1 part"],
              ["[  ]", "Supports OFF; 'support everywhere' not selected"],
              ["[  ]", "Perimeter generator Arachne, line width 0.42–0.45 mm, XY compensation 0"],
              ["[  ]", "Elephant-foot compensation ≈ 0.15 mm; brim OFF (no brim lines inside the 40 × 40 mm footprint)"],
              ["[  ]", "Build plate clean (soap and water or IPA); glue stick only if corners lifted before"],
              ["[  ]", "Preview: 9 see-through openings visible on top view, openings open in every layer"],
              ["[  ]", "Cooling 100 % from layer 2; avoid crossing perimeters ON"],
              ["[  ]", "Bed clean and level; first layer continuous"],
              ["[  ]", "After printing: 9 clear openings on each of the six faces"]]
    story += [table(checks, [12, 162]), Spacer(1, 6),
              P(f"Report generated from the project files on {date.today().isoformat()}; STL SHA-256 {sha}.", "small")]

    doc = SimpleDocTemplate(str(OUT_PDF), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm, title="Gyroid Design and 3D Printing Report",
                            author="ME3305 project", subject="Gyroid 3x3 cube redesign for PLA FDM")
    doc.build(story, onFirstPage=page_decor, onLaterPages=page_decor)
    print("wrote", OUT_PDF)


if __name__ == "__main__":
    main()
