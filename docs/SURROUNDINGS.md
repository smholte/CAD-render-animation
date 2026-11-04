# Surroundings and 360° photos

Panel **5 Scene & Render**, setting **Background**. Pick where the machine stands; its
settings appear right below the choice.

| Group | Background | What you get |
| --- | --- | --- |
| Studio | Solid colour, None (transparent), Sky | As before: a clean background with studio light or sun. |
| Photo | 360° photo | A photo from your library is the background and the light. With **Stand on its ground** ticked, the photo's floor lies flat under the machine and catches its shadow. |
| Offshore | Open sea, Vessel deck, Quayside | Sea to the horizon under a sky with a sun. Calm or rough, foam, waves that move in videos. |
| Workshop | Clean factory hall, CNC machining hall, Assembly hall, Warehouse | A hall built around the machine: floor with walkway lines, columns, roof trusses, light lines, machines, racks, an overhead crane. |

Everything in the offshore and workshop surroundings is made by the app itself (no photos,
nothing to download). The surroundings grow with the machine: a bigger machine gets a bigger
hall or deck.

## How it behaves

- **The machine stands on the floor.** Its lowest point is put on the floor, deck or quay,
  centred. The machine itself is never moved, so joints, poses, cameras and videos stay as
  they are. Parts you hide (Show only, or a saved scene that hides covers) do not move the
  floor; parts removed in Clean-up do.
- **Simple / Detailed.** Simple puts fewer things around the machine and renders fastest.
  Detailed adds more (containers, a deckhouse, workbenches, more racks, real waves on the
  sea near the machine). Times are below.
- **Halls never hide the machine.** The walls are only seen from the inside: a camera
  outside the hall looks straight in. Anything that would stand between the camera and the
  machine (a column, a rack, a truss) is left out of the picture, and when the camera is
  higher than the light lines the roof structure is left out too, so you look into the hall
  from above. Light, shadows and reflections still include everything.
- **Floor gap and "Put on the floor again"** are in the **More** fold. Use the button after
  you changed the machine (another model revision, parts removed in Clean-up).
- **Show in the view** (in **More**) hides the surroundings while you work; renders always
  include them.
- Saved scenes, templates and the render queue keep the surroundings.

## Props for scale

Sub-panel **Props for scale** under 5 Scene & Render: **Person** (1.8 m), **20 ft
container**, **Euro pallet**, **Safety barrier**. Each click puts one next to the machine on
the floor and selects it: move it with the arrows in the view (or press G), turn it with R,
delete it with X. **Show props** hides or shows all of them in one click (also per saved
scene); **Delete all** removes them.

## Render times

Measured on the 2-core test machine (processor only, no graphics card), 640 × 360 pixels,
quality Preview, the crane test model enlarged to 6.4 × 2.4 × 2.0 m, the camera a bit further
away than "Fit" so the surroundings fill the picture. One render each:

| Background | Simple | Detailed | Compared with the studio |
| --- | --- | --- | --- |
| Studio (solid colour, shadow floor) | 31.2 s | – | 1 |
| 360° photo, Stand on its ground off / on | 29.2 s / 25.1 s | – | 0.8–0.9 |
| Open sea | 29.2 s | 30.3 s | 0.9–1.0 |
| Vessel deck | 28.3 s | 29.9 s | 0.9–1.0 |
| Quayside | 25.9 s | 30.3 s | 0.8–1.0 |
| Clean factory hall | 48.4 s | 62.7 s | 1.6–2.0 |
| CNC machining hall | 69.8 s | 86.6 s | 2.2–2.8 |
| Assembly hall | 43.1 s | 48.1 s | 1.4–1.5 |
| Warehouse | 52.3 s | 81.3 s | 1.7–2.6 |

Building a surrounding takes less than half a second. Offshore and photo surroundings cost
no extra time; halls cost 1.4 to 2.8 times the studio, because there is much more to see and to
reflect. For long videos in a hall, use **Simple**. On your RTX 3090 everything is much faster;
whether the halls cost the same factor there is not measured yet (expectation: similar).

## Getting 360° photos

The app does not ship photos: you put them in the shared library once and then pick them
with one click. Good free photos (licence CC0: free for any use, also commercial, no credit
needed) come from **Poly Haven**.

### Recommended photos

Workshops and halls (indoor; best with **Stand on its ground** on):

| Photo | Page | Good for |
| --- | --- | --- |
| Machine Shop 02 | https://polyhaven.com/a/machine_shop_02 | CNC mills and machine tools in a workshop hall, daylight |
| Industrial Workshop Foundry | https://polyhaven.com/a/industrial_workshop_foundry | Heavy industry, steel construction |
| Aircraft Workshop 01 | https://polyhaven.com/a/aircraft_workshop_01 | Large machines in a big assembly hall |
| Small Hangar 01 | https://polyhaven.com/a/small_hangar_01 | Clean, bright hall with daylight; large machines |
| Small Hangar 02 | https://polyhaven.com/a/small_hangar_02 | As above, more contrast |
| Empty Warehouse 01 | https://polyhaven.com/a/empty_warehouse_01 | Warehouse with fluorescent light |
| Industrial Pipe & Valve 02 | https://polyhaven.com/a/industrial_pipe_and_valve_02 | Warehouse interior with daylight from an open door |
| Empty Workshop | https://polyhaven.com/a/empty_workshop | Clean, empty workshop; calm background for brochures |

Harbour, coast and outdoor industry:

| Photo | Page | Good for |
| --- | --- | --- |
| Simon's Town Harbour | https://polyhaven.com/a/simons_town_harbour | Machine on a quay in a harbour, sunny |
| Abandoned Slipway | https://polyhaven.com/a/abandoned_slipway | Industrial waterfront, overcast (soft light, no hard shadows) |
| Docklands 02 | https://polyhaven.com/a/docklands_02 | Quay along a river in a city, sunny |
| Freight Station | https://polyhaven.com/a/freight_station | Industrial yard with cranes, low sun |
| Fish Hoek Beach | https://polyhaven.com/a/fish_hoek_beach | Sea in the background, overcast; turn **Stand on its ground** off |
| Blouberg Sunrise 2 | https://polyhaven.com/a/blouberg_sunrise_2 | Sea and sky at sunrise; turn **Stand on its ground** off |

Photos with a flat floor (halls, quays, yards) work best with **Stand on its ground**. For a
beach or hills, turn it off: the photo stays far away and the normal **Floor** setting is
used (Shadow only works well).

### Click steps

**Once: tell the app where the library is**

1. Make a folder for the library, for example `D:\Fresing library` (or a folder on the
   network that everyone uses). Inside it, make a folder `HDRI`. You can sort the photos in
   sub-folders, for example `HDRI\Halls` and `HDRI\Harbour`.
2. In Fresing Render: **Edit** menu > **Preferences** > **Add-ons**. Type `Fresing` in the
   search box and click the arrow in front of **Fresing Render** to open it.
3. Next to **Shared library**, click the folder button, pick your library folder (the one that
   contains `HDRI`), click **Accept**.
4. Close the Preferences window (it saves by itself).

**For each photo**

1. Open the photo's page from the lists above in your web browser.
2. On the right, set the resolution to **4K** (enough for backgrounds; take **8K** if the
   background is sharp and large in the picture) and the format to **EXR** (or HDR).
3. Click **Download**. Move the file into your library's `HDRI` folder (or a sub-folder).

**Use it**

1. Panel **5 Scene & Render** > **Background**: pick **360° photo**.
2. Click the library button next to **Photo** (the small icon on the right) and click the
   photo in the list. Type part of its name to search.
3. Leave **Stand on its ground** ticked. Change **Photo taken at** (most photos are taken
   at 1.5-2 m) until the machine has the right size against the photo's floor.
4. **Turn photo** turns the photo around the machine: turn it until the light and the
   background suit the machine. Use **Live preview** to see it while you drag.
