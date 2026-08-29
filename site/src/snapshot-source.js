let selectedSnapshotPromise;

function deepFreeze(value, seen = new WeakSet()) {
  if (!value || typeof value !== 'object' || seen.has(value)) return value;
  seen.add(value);
  Object.freeze(value);
  Object.values(value).forEach((child) => deepFreeze(child, seen));
  return value;
}

export function loadSelectedSealedSnapshot(fetcher = fetch) {
  if (!selectedSnapshotPromise) {
    selectedSnapshotPromise = fetcher('/data/run34.json', { cache: 'no-store' }).then(async (response) => {
      if (!response.ok) throw new Error(`Snapshot request failed: HTTP ${response.status}`);
      const snapshot = await response.json();
      if (snapshot.run?.status !== 'SEALED') throw new Error(`Selected generation is not SEALED: ${snapshot.run?.status || 'UNKNOWN'}`);
      return deepFreeze(snapshot);
    });
  }
  return selectedSnapshotPromise;
}

export function resetSelectedSnapshotForTests() {
  selectedSnapshotPromise = undefined;
}
