#!/usr/bin/python3
"""Offscreen 3D render of a KiCad STEP export (colours from the STEP's XCAF data).
usage: render3d.py board.step out.png [elev_deg azim_deg width height]"""
import math, os, sys
import numpy as np
import pyvista as pv
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_ColorType
from OCP.TDF import TDF_Label, TDF_ChildIterator
from OCP.Quantity import Quantity_Color
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCP.TopoDS import TopoDS
from OCP.BRep import BRep_Tool
from OCP.TopLoc import TopLoc_Location


def load(path):
    doc = TDocStd_Document(TCollection_ExtendedString('doc'))
    r = STEPCAFControl_Reader(); r.SetColorMode(True); r.SetNameMode(True)
    r.ReadFile(path); r.Transfer(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main()); ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    return st, ct, doc          # keep doc alive: labels die with it


def faces_with_colour(st, ct):
    out = []

    def colour(label, fallback):
        c = Quantity_Color()
        for t in (XCAFDoc_ColorType.XCAFDoc_ColorSurf, XCAFDoc_ColorType.XCAFDoc_ColorGen):
            if ct.GetColor_s(label, t, c):
                return (c.Red(), c.Green(), c.Blue())
        return fallback

    def children(label):
        it = TDF_ChildIterator(label, False)
        while it.More():
            yield it.Value(); it.Next()

    def walk(label, loc, col):
        col = colour(label, col)
        if st.IsAssembly_s(label):
            for cl in children(label):
                ref = TDF_Label()
                if not st.GetReferredShape_s(cl, ref):
                    continue
                walk(ref, loc.Multiplied(st.GetLocation_s(cl)), colour(cl, col))
            return
        shape = st.GetShape_s(label).Moved(loc)
        BRepMesh_IncrementalMesh(shape, 0.05, False, 0.3, True)
        facecol = {}
        for sl in children(label):            # coloured sub-shapes (faces / solids)
            c = colour(sl, None)
            if c is None:
                continue
            ex2 = TopExp_Explorer(st.GetShape_s(sl).Moved(loc), TopAbs_FACE)
            while ex2.More():
                facecol[ex2.Current().__hash__()] = c; ex2.Next()
        ex = TopExp_Explorer(shape, TopAbs_FACE)
        while ex.More():
            f = TopoDS.Face(ex.Current())
            fc = facecol.get(ex.Current().__hash__(), col)
            l = TopLoc_Location(); tri = BRep_Tool.Triangulation_s(f, l)
            if tri is not None:
                tr = l.Transformation()
                v = np.array([[p.X(), p.Y(), p.Z()] for p in
                              (tri.Node(i).Transformed(tr) for i in range(1, tri.NbNodes() + 1))])
                t = np.array([tri.Triangle(i).Get() for i in range(1, tri.NbTriangles() + 1)]) - 1
                if f.Orientation() == TopAbs_REVERSED:
                    t = t[:, ::-1]
                out.append((v, t, fc))
            ex.Next()

    for top in children(st.Label()):
        if st.IsTopLevel(top) if hasattr(st, 'IsTopLevel') else True:
            if st.IsFree_s(top) if hasattr(st, 'IsFree_s') else True:
                walk(top, TopLoc_Location(), (0.6, 0.6, 0.6))
    return out


def main(step, png, elev='35', azim='-60', w='1400', h='1000'):
    st, ct, doc = load(step)
    parts = faces_with_colour(st, ct)
    groups = {}
    for v, t, c in parts:
        groups.setdefault(tuple(round(x, 3) for x in c), []).append((v, t))
    pv.OFF_SCREEN = True
    p = pv.Plotter(off_screen=True, window_size=(int(w), int(h)))
    p.set_background('#1f1f21')
    allv = []
    for c, items in groups.items():
        vs, fs, off = [], [], 0
        for v, t in items:
            vs.append(v); fs.append(np.hstack([np.full((len(t), 1), 3), t + off])); off += len(v)
        mesh = pv.PolyData(np.vstack(vs), np.vstack(fs).ravel())
        shiny = min(c) > 0.6
        p.add_mesh(mesh, color=c, smooth_shading=False, specular=0.5 if shiny else 0.15, specular_power=25)
        allv.append(np.vstack(vs))
    allv = np.vstack(allv); lo, hi = allv.min(0), allv.max(0); ctr = (lo + hi) / 2; size = np.linalg.norm(hi - lo)
    e, a = math.radians(float(elev)), math.radians(float(azim))
    eye = ctr + size * float(os.environ.get('CAM_DIST', '1.75')) * np.array([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)])
    p.camera_position = [tuple(eye), tuple(ctr), (0, 0, 1)]
    p.camera.view_angle = 30
    p.enable_anti_aliasing('ssaa')
    p.screenshot(png)
    print('rendered', png, len(parts), 'faces', len(groups), 'colours')


if __name__ == '__main__':
    main(*sys.argv[1:])
