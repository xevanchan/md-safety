/* Maryland inspection station finder. Plain JavaScript, no build step. */
(async () => {
  const STYLE_URL = "https://tiles.openfreemap.org/styles/liberty";
  const MARYLAND = [
    [-79.6, 37.85],
    [-74.9, 39.8],
  ]; // [west, south], [east, north]
  const PAGE = 25;

  const $ = (id) => document.getElementById(id);
  const status = $("status");
  const list = $("list");
  const more = $("more");

  let data;
  let zips;
  try {
    [data, zips] = await Promise.all([
      fetch("data/stations.json").then((r) => r.json()),
      fetch("data/zips.json").then((r) => r.json()),
    ]);
  } catch (err) {
    status.textContent = "Couldn't load the station list. Please try again later.";
    console.error(err);
    return;
  }
  const stations = data.stations.filter((s) => s.lat != null);
  const byId = new Map(stations.map((s) => [s.id, s]));
  $("fetched").textContent = (data.fetched_at || "").slice(0, 10) || "an unknown date";

  let origin = null; // {lat, lon, label}
  let shown = PAGE;
  let selectedId = null;

  const map = new maplibregl.Map({
    container: "map",
    style: STYLE_URL,
    bounds: MARYLAND,
    attributionControl: false,
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }));
  map.addControl(new maplibregl.AttributionControl({ compact: true }));
  const here = new maplibregl.Marker({ color: "#dc2626" });
  const popup = new maplibregl.Popup({ maxWidth: "260px" });

  map.on("load", () => {
    map.addSource("stations", {
      type: "geojson",
      data: {
        type: "FeatureCollection",
        features: stations.map((s) => ({
          type: "Feature",
          geometry: { type: "Point", coordinates: [s.lon, s.lat] },
          // One truthy property per class, so the layer filter can use ["has", class].
          properties: Object.fromEntries([["id", s.id], ...s.classes.map((c) => [c, 1])]),
        })),
      },
    });
    map.addLayer({
      id: "stations",
      type: "circle",
      source: "stations",
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 6, 3, 12, 7],
        "circle-color": "#1d4ed8",
        "circle-opacity": 0.8,
        "circle-stroke-color": "#ffffff",
        "circle-stroke-width": 1,
      },
    });
    map.addLayer({
      id: "selected",
      type: "circle",
      source: "stations",
      filter: ["==", ["get", "id"], -1],
      paint: {
        "circle-radius": 11,
        "circle-color": "#f59e0b",
        "circle-stroke-color": "#ffffff",
        "circle-stroke-width": 2,
      },
    });
    map.on("click", "stations", (e) => select(e.features[0].properties.id, { fromMap: true }));
    map.on("mouseenter", "stations", () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", "stations", () => (map.getCanvas().style.cursor = ""));
    render(); // apply the class filter to the dots once the layers exist
  });
  render(); // the list and status work even before (or without) the map tiles

  function haversineMiles(a, b) {
    const toRad = (d) => (d * Math.PI) / 180;
    const dLat = toRad(b.lat - a.lat);
    const dLon = toRad(b.lon - a.lon);
    const h =
      Math.sin(dLat / 2) ** 2 +
      Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLon / 2) ** 2;
    return 2 * 3958.8 * Math.asin(Math.sqrt(h));
  }

  const esc = (text) =>
    String(text).replace(
      /[&<>"']/g,
      (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
    );

  function matching() {
    const cls = $("class").value;
    return cls ? stations.filter((s) => s.classes.includes(cls)) : stations.slice();
  }

  function setSelectedOnMap(id) {
    if (map.getLayer("selected")) map.setFilter("selected", ["==", ["get", "id"], id]);
  }

  function render() {
    const cls = $("class").value;
    if (map.getLayer("stations")) map.setFilter("stations", cls ? ["has", cls] : null);
    const rows = matching();
    if (!origin) {
      list.innerHTML = "";
      more.hidden = true;
      status.textContent = `${rows.length} stations across Maryland. Use your location or a ZIP code to sort them by distance.`;
      return rows;
    }
    for (const s of rows) s.miles = haversineMiles(origin, s);
    rows.sort((a, b) => a.miles - b.miles);
    status.textContent = `${rows.length} stations, nearest first from ${origin.label}.`;
    list.innerHTML = rows.slice(0, shown).map(item).join("");
    more.hidden = rows.length <= shown;
    return rows;
  }

  function item(s) {
    const address = `${s.address}, ${s.city}, MD ${s.zip}`;
    const directions =
      "https://www.google.com/maps/dir/?api=1&destination=" + encodeURIComponent(address);
    const phone = s.phone
      ? `<a href="tel:${s.phone.replace(/\D/g, "")}">${esc(s.phone)}</a>`
      : "";
    const approx = s.approx ? ' <span class="approx">approximate location</span>' : "";
    const selected = s.id === selectedId ? " selected" : "";
    return `<li class="station${selected}" data-id="${s.id}" tabindex="0">
      <div class="row"><span class="name">${esc(s.name)}</span><span class="miles">${s.miles.toFixed(1)} mi</span></div>
      <div class="addr">${esc(address)}${approx}</div>
      <div class="meta">${phone}<span>Classes ${esc(s.classes.join(", "))}</span><a href="${directions}" target="_blank" rel="noopener">Directions</a></div>
    </li>`;
  }

  function select(id, { fromMap = false } = {}) {
    const s = byId.get(id);
    if (!s) return;
    selectedId = id;
    setSelectedOnMap(id);
    if (!fromMap) map.flyTo({ center: [s.lon, s.lat], zoom: Math.max(map.getZoom(), 13) });
    popup
      .setLngLat([s.lon, s.lat])
      .setHTML(
        `<strong>${esc(s.name)}</strong><br>${esc(s.address)}<br>${esc(s.city)}, MD ${esc(s.zip)}`
      )
      .addTo(map);
    for (const li of list.querySelectorAll(".selected")) li.classList.remove("selected");
    const li = list.querySelector(`[data-id="${id}"]`);
    if (li) {
      li.classList.add("selected");
      if (fromMap) li.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }

  function setOrigin(next) {
    origin = next;
    shown = PAGE;
    selectedId = null;
    popup.remove();
    setSelectedOnMap(-1);
    here.setLngLat([next.lon, next.lat]).addTo(map);
    const rows = render();
    const bounds = new maplibregl.LngLatBounds([next.lon, next.lat], [next.lon, next.lat]);
    for (const s of rows.slice(0, 10)) bounds.extend([s.lon, s.lat]);
    map.fitBounds(bounds, { padding: 48, maxZoom: 13, duration: 800 });
  }

  $("locate").addEventListener("click", () => {
    if (!navigator.geolocation) {
      status.textContent = "This browser can't share your location. Enter a ZIP code instead.";
      return;
    }
    status.textContent = "Finding your location…";
    navigator.geolocation.getCurrentPosition(
      (pos) =>
        setOrigin({ lat: pos.coords.latitude, lon: pos.coords.longitude, label: "your location" }),
      (err) => {
        const why =
          err.code === err.PERMISSION_DENIED
            ? "Location access was denied."
            : "Couldn't get your location.";
        status.textContent = `${why} Enter a ZIP code instead.`;
      },
      { timeout: 10000, maximumAge: 300000 }
    );
  });

  $("controls").addEventListener("submit", (e) => {
    e.preventDefault();
    const zip = $("zip").value.trim();
    const centre = zips[zip];
    if (!centre) {
      status.textContent = /^\d{5}$/.test(zip)
        ? `${zip} isn't a Maryland ZIP code we know. Try a nearby one.`
        : "Enter a five-digit Maryland ZIP code.";
      return;
    }
    setOrigin({ lat: centre[0], lon: centre[1], label: `ZIP ${zip}` });
  });

  $("class").addEventListener("change", () => {
    shown = PAGE;
    render();
  });

  more.addEventListener("click", () => {
    shown += PAGE;
    render();
  });

  list.addEventListener("click", (e) => {
    if (e.target.closest("a")) return; // let phone and directions links work
    const li = e.target.closest(".station");
    if (li) select(Number(li.dataset.id));
  });

  list.addEventListener("keydown", (e) => {
    if ((e.key !== "Enter" && e.key !== " ") || !e.target.classList.contains("station")) return;
    e.preventDefault();
    select(Number(e.target.dataset.id));
  });
})();
