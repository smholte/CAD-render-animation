"""Small triangle meshes for the weld tests (task 0319), made like the importer makes them: every CAD face has its own
points (two faces never share a point), outward normals. Metres."""

import numpy as np, math
def box(lo, hi):
    """Box with each face its own 4 points (as the importer: faces don't share points). Returns pts, tris, face."""
    lo, hi = np.array(lo, float), np.array(hi, float)
    c = lambda i,j,k: [ (lo,hi)[i][0], (lo,hi)[j][1], (lo,hi)[k][2] ]
    quads = [  # outward winding
        [c(0,0,0), c(0,1,0), c(1,1,0), c(1,0,0)],  # -z
        [c(0,0,1), c(1,0,1), c(1,1,1), c(0,1,1)],  # +z
        [c(0,0,0), c(1,0,0), c(1,0,1), c(0,0,1)],  # -y
        [c(0,1,0), c(0,1,1), c(1,1,1), c(1,1,0)],  # +y
        [c(0,0,0), c(0,0,1), c(0,1,1), c(0,1,0)],  # -x
        [c(1,0,0), c(1,1,0), c(1,1,1), c(1,0,1)],  # +x
    ]
    pts, tris, face = [], [], []
    for f,q in enumerate(quads):
        b=len(pts); pts += q
        tris += [[b,b+1,b+2],[b,b+2,b+3]]; face += [f,f]
    return np.array(pts), np.array(tris), np.array(face)

def cylinder(r, z0, z1, n=32, centre=(0,0), axis='z', inside=False, caps=True):
    """Tube outer face (face 0), caps (faces 1, 2)."""
    a = np.linspace(0, 2*np.pi, n, endpoint=False)
    ring = np.stack([centre[0]+r*np.cos(a), centre[1]+r*np.sin(a)],1)
    pts=[]; tris=[]; face=[]
    for (x,y) in ring: pts.append([x,y,z0])
    for (x,y) in ring: pts.append([x,y,z1])
    for i in range(n):
        j=(i+1)%n
        t1=[i,j,n+j]; t2=[i,n+j,n+i]
        if inside: t1=t1[::-1]; t2=t2[::-1]
        tris += [t1,t2]; face+=[0,0]
    if caps:
        for f,z,sgn in ((1,z0,-1),(2,z1,1)):
            b=len(pts); pts.append([centre[0],centre[1],z])
            for (x,y) in ring: pts.append([x,y,z])
            for i in range(n):
                j=(i+1)%n
                t=[b, b+1+i, b+1+j] if sgn>0 else [b, b+1+j, b+1+i]
                tris.append(t); face.append(f)
    return np.array(pts,float), np.array(tris), np.array(face)

def merge(*meshes):
    P=[];T=[];F=[];off=0;foff=0
    for p,t,f in meshes:
        P.append(p);T.append(t+off);F.append(f+foff);off+=len(p);foff+=f.max()+1
    return np.concatenate(P),np.concatenate(T),np.concatenate(F)

def along_y(p, t, f):
    """The same mesh turned so its z axis runs along y (swapping y and z mirrors it: the triangles are turned back)."""
    return p[:, [0, 2, 1]].copy(), t[:, ::-1].copy(), f

def plate_with_hole(half, r, z0, z1, n=32):
    """Square plate +-half in x,y, z0..z1, a round hole radius r at the centre. Faces: 0 top, 1 bottom, 2 hole, 3-6 sides."""
    a = np.linspace(0, 2*np.pi, n, endpoint=False)
    circ = np.stack([r*np.cos(a), r*np.sin(a)],1)
    sq = np.stack([np.cos(a), np.sin(a)],1)
    sq = sq/np.abs(sq).max(1,keepdims=True)*half
    pts=[];tris=[];face=[]
    for f,z,up in ((0,z1,True),(1,z0,False)):
        b=len(pts)
        for p in circ: pts.append([p[0],p[1],z])
        for p in sq: pts.append([p[0],p[1],z])
        for i in range(n):
            j=(i+1)%n
            t1=[b+i,b+n+i,b+n+j]; t2=[b+i,b+n+j,b+j]
            if not up: t1=t1[::-1]; t2=t2[::-1]
            tris+=[t1,t2]; face+=[f,f]
    hp,ht,hf = cylinder(r, z0, z1, n, inside=True, caps=False)
    b=len(pts); pts+=hp.tolist(); tris+=(ht+b).tolist(); face+=[2]*len(ht)
    # four sides (corners of the square are points of sq at 45 deg only when n%8==0)
    P=np.array(pts,float);T=np.array(tris);F=np.array(face)
    sides=[box((-half,-half,z0),(half,half,z1))]
    bp,bt,bf=sides[0]
    keep=bf>=2   # -y,+y,-x,+x of the box
    # map box faces 2..5 to faces 3..6
    sel=np.isin(np.arange(len(bt)), np.flatnonzero(keep))
    bt=bt[sel]; bf=bf[sel]+1
    T=np.concatenate([T,bt+len(P)]); F=np.concatenate([F,bf]); P=np.concatenate([P,bp])
    return P,T,F

def tube_coped(r, R, ztop, n=32):
    """Tube radius r along z from the surface of a tube radius R along y (axis through the origin) up to ztop."""
    a = np.linspace(0, 2*np.pi, n, endpoint=False)
    x, y = r*np.cos(a), r*np.sin(a)
    zb = np.sqrt(R*R - x*x)
    pts=[];tris=[];face=[]
    for i in range(n): pts.append([x[i],y[i],zb[i]])
    for i in range(n): pts.append([x[i],y[i],ztop])
    for i in range(n):
        j=(i+1)%n; tris+=[[i,j,n+j],[i,n+j,n+i]]; face+=[0,0]
    b=len(pts); pts.append([0,0,ztop])
    for i in range(n): pts.append([x[i],y[i],ztop])
    for i in range(n): j=(i+1)%n; tris.append([b,b+1+i,b+1+j]); face.append(1)
    # the coped end closed by a fan (a solid bar: enough for the finder)
    b=len(pts); 
    for i in range(n): pts.append([x[i],y[i],zb[i]])
    pts.append([0,0,R*0.9])
    for i in range(n): j=(i+1)%n; tris.append([b+n,b+j,b+i]); face.append(2)
    return np.array(pts,float),np.array(tris),np.array(face)
