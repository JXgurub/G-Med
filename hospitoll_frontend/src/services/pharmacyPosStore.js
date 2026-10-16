const DATABASE_NAME = 'gmed-pharmacy-pos'
const DATABASE_VERSION = 1

let databasePromise

const openDatabase = () => {
  if (typeof indexedDB === 'undefined') {
    return Promise.reject(new Error('Ushbu brauzer lokal dorixona ma’lumotlarini saqlashni qo‘llamaydi.'))
  }
  if (databasePromise) return databasePromise

  databasePromise = new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE_NAME, DATABASE_VERSION)
    request.onupgradeneeded = () => {
      const database = request.result
      if (!database.objectStoreNames.contains('metadata')) {
        database.createObjectStore('metadata', { keyPath: 'key' })
      }
      if (!database.objectStoreNames.contains('medicines')) {
        database.createObjectStore('medicines', { keyPath: 'id' })
      }
      if (!database.objectStoreNames.contains('inventory')) {
        database.createObjectStore('inventory', { keyPath: 'cacheId' })
      }
      if (!database.objectStoreNames.contains('sales')) {
        database.createObjectStore('sales', { keyPath: 'id' })
      }
    }
    request.onsuccess = () => {
      request.result.onversionchange = () => request.result.close()
      resolve(request.result)
    }
    request.onerror = () => {
      databasePromise = null
      reject(request.error || new Error('Lokal ma’lumotlar bazasini ochib bo‘lmadi.'))
    }
  })

  return databasePromise
}

const withTransaction = async (storeNames, mode, run) => {
  const database = await openDatabase()
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(storeNames, mode)
    let value
    transaction.oncomplete = () => resolve(value)
    transaction.onerror = () => reject(transaction.error || new Error('Lokal ma’lumotlar bazasi xatosi.'))
    transaction.onabort = () => reject(transaction.error || new Error('Lokal saqlash bekor qilindi.'))
    try {
      value = run(transaction)
    } catch (error) {
      transaction.abort()
      reject(error)
    }
  })
}

const cacheInventoryId = (pharmacyId, inventoryId) => `${pharmacyId}:${inventoryId}`

export const getOrCreatePosClientId = (pharmacyId) => {
  const clientStorageKey = `gmed_pharmacy_pos_client_id:${pharmacyId}`
  let clientId = localStorage.getItem(clientStorageKey)
  if (!clientId) {
    if (!globalThis.crypto?.randomUUID) {
      throw new Error('Kompyuterni ro‘yxatdan o‘tkazish uchun zamonaviy brauzer kerak.')
    }
    clientId = globalThis.crypto.randomUUID()
    localStorage.setItem(clientStorageKey, clientId)
  }
  return clientId
}

export const rotatePosClientId = (pharmacyId) => {
  localStorage.removeItem(`gmed_pharmacy_pos_client_id:${pharmacyId}`)
  return getOrCreatePosClientId(pharmacyId)
}

export const savePosSnapshot = async (snapshot) => {
  const pharmacyId = String(snapshot?.pharmacy?.id || '')
  if (!pharmacyId || !Array.isArray(snapshot?.medicines) || !Array.isArray(snapshot?.inventory)) {
    throw new Error('Serverdan kelgan dorixona ma’lumotlari noto‘g‘ri.')
  }

  await withTransaction(['metadata', 'medicines', 'inventory'], 'readwrite', (transaction) => {
    const medicineStore = transaction.objectStore('medicines')
    const inventoryStore = transaction.objectStore('inventory')
    const metadataStore = transaction.objectStore('metadata')
    const existingRequest = inventoryStore.getAll()
    existingRequest.onsuccess = () => {
      existingRequest.result
        .filter((item) => item.pharmacy_id === pharmacyId)
        .forEach((item) => inventoryStore.delete(item.cacheId))
      snapshot.inventory.forEach((item) => inventoryStore.put({
        ...item,
        pharmacy_id: pharmacyId,
        cacheId: cacheInventoryId(pharmacyId, item.id),
      }))
    }
    medicineStore.clear()
    snapshot.medicines.forEach((medicine) => medicineStore.put(medicine))
    const metadataRequest = metadataStore.get(`snapshot:${pharmacyId}`)
    metadataRequest.onsuccess = () => {
      metadataStore.put({
        key: `snapshot:${pharmacyId}`,
        pharmacy: { ...(metadataRequest.result?.pharmacy || {}), ...snapshot.pharmacy },
        snapshotAt: snapshot.snapshot_at || new Date().toISOString(),
      })
    }
    metadataStore.put({ key: 'last-pharmacy-id', id: pharmacyId })
  })
}

export const savePosInventory = async (pharmacyId, rows) => {
  await withTransaction(['inventory'], 'readwrite', (transaction) => {
    const store = transaction.objectStore('inventory')
    const existingRequest = store.getAll()
    existingRequest.onsuccess = () => {
      existingRequest.result
        .filter((item) => item.pharmacy_id === String(pharmacyId))
        .forEach((item) => store.delete(item.cacheId))
      rows.forEach((item) => store.put({
        ...item,
        pharmacy_id: String(pharmacyId),
        cacheId: cacheInventoryId(pharmacyId, item.id),
      }))
    }
  })
}

export const saveCachedPharmacy = async (pharmacy) => {
  if (!pharmacy?.id) return
  await withTransaction(['metadata'], 'readwrite', (transaction) => {
    const store = transaction.objectStore('metadata')
    store.put({
      key: `snapshot:${pharmacy.id}`,
      pharmacy,
      snapshotAt: new Date().toISOString(),
    })
    store.put({ key: 'last-pharmacy-id', id: String(pharmacy.id) })
  })
}

export const getLastCachedPharmacy = async () => {
  const database = await openDatabase()
  return new Promise((resolve, reject) => {
    const transaction = database.transaction('metadata', 'readonly')
    const store = transaction.objectStore('metadata')
    const idRequest = store.get('last-pharmacy-id')
    let pharmacyId = null
    idRequest.onsuccess = () => {
      pharmacyId = idRequest.result?.id || null
      if (!pharmacyId) return
      const pharmacyRequest = store.get(`snapshot:${pharmacyId}`)
      pharmacyRequest.onsuccess = () => resolve(pharmacyRequest.result?.pharmacy || null)
      pharmacyRequest.onerror = () => reject(pharmacyRequest.error || new Error('Lokal dorixona ma’lumotini o‘qib bo‘lmadi.'))
    }
    idRequest.onerror = () => reject(idRequest.error || new Error('Lokal dorixona ma’lumotini o‘qib bo‘lmadi.'))
    transaction.oncomplete = () => {
      if (!pharmacyId) resolve(null)
    }
  })
}

export const savePosCatalog = async (pharmacy, medicines) => {
  await withTransaction(['metadata', 'medicines'], 'readwrite', (transaction) => {
    const medicineStore = transaction.objectStore('medicines')
    const metadataStore = transaction.objectStore('metadata')
    medicineStore.clear()
    medicines.forEach((medicine) => medicineStore.put(medicine))
    if (pharmacy?.id) {
      metadataStore.put({
        key: `snapshot:${pharmacy.id}`,
        pharmacy,
        snapshotAt: new Date().toISOString(),
      })
      metadataStore.put({ key: 'last-pharmacy-id', id: String(pharmacy.id) })
    }
  })
}

export const getPosSnapshot = async (pharmacyId) => {
  const database = await openDatabase()
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(['metadata', 'medicines', 'inventory'], 'readonly')
    const metadataRequest = transaction.objectStore('metadata').get(`snapshot:${pharmacyId}`)
    const medicineRequest = transaction.objectStore('medicines').getAll()
    const inventoryRequest = transaction.objectStore('inventory').getAll()
    let metadata
    let medicines
    let inventory

    metadataRequest.onsuccess = () => { metadata = metadataRequest.result }
    medicineRequest.onsuccess = () => { medicines = medicineRequest.result }
    inventoryRequest.onsuccess = () => { inventory = inventoryRequest.result }
    transaction.oncomplete = () => {
      if (!metadata) {
        resolve(null)
        return
      }
      resolve({
        pharmacy: metadata.pharmacy,
        snapshot_at: metadata.snapshotAt,
        medicines: medicines || [],
        inventory: (inventory || []).filter((item) => item.pharmacy_id === String(pharmacyId)),
      })
    }
    transaction.onerror = () => reject(transaction.error || new Error('Lokal ma’lumotlarni o‘qib bo‘lmadi.'))
  })
}

export const getCachedPharmacy = async (pharmacyId) => {
  const database = await openDatabase()
  return new Promise((resolve, reject) => {
    const transaction = database.transaction('metadata', 'readonly')
    const request = transaction.objectStore('metadata').get(`snapshot:${pharmacyId}`)
    request.onsuccess = () => resolve(request.result?.pharmacy || null)
    request.onerror = () => reject(request.error || new Error('Lokal dorixona ma’lumotini o‘qib bo‘lmadi.'))
  })
}

export const saveActivatedPosDevice = async (pharmacyId, device) => {
  await withTransaction(['metadata'], 'readwrite', (transaction) => {
    transaction.objectStore('metadata').put({ key: `pos-device:${pharmacyId}`, device })
  })
}

export const getActivatedPosDevice = async (pharmacyId) => {
  const database = await openDatabase()
  return new Promise((resolve, reject) => {
    const transaction = database.transaction('metadata', 'readonly')
    const request = transaction.objectStore('metadata').get(`pos-device:${pharmacyId}`)
    request.onsuccess = () => resolve(request.result?.device || null)
    request.onerror = () => reject(request.error || new Error('Kassir kompyuteri ma’lumotini o‘qib bo‘lmadi.'))
  })
}

export const saveOfflineSale = async (sale) => {
  const pharmacyId = String(sale.pharmacy_id)
  await withTransaction(['sales', 'inventory'], 'readwrite', (transaction) => {
    transaction.objectStore('sales').add({ ...sale, status: 'pending', has_stock_discrepancy: false })
    const inventoryStore = transaction.objectStore('inventory')
    sale.lines.forEach((line) => {
      if (!line.inventory_id) return
      const cacheId = cacheInventoryId(pharmacyId, line.inventory_id)
      const request = inventoryStore.get(cacheId)
      request.onsuccess = () => {
        const inventory = request.result
        if (!inventory) return
        inventory.quantity_in_stock = Math.max(0, Number(inventory.quantity_in_stock || 0) - line.quantity)
        inventoryStore.put(inventory)
      }
    })
  })
}

export const getPendingOfflineSales = async (pharmacyId) => {
  const database = await openDatabase()
  return new Promise((resolve, reject) => {
    const transaction = database.transaction('sales', 'readonly')
    const request = transaction.objectStore('sales').getAll()
    request.onsuccess = () => resolve(request.result.filter(
      (sale) => sale.pharmacy_id === String(pharmacyId) && sale.status === 'pending',
    ))
    request.onerror = () => reject(request.error || new Error('Kutayotgan sotuvlarni o‘qib bo‘lmadi.'))
  })
}

export const markOfflineSaleSynced = async (saleId, hasStockDiscrepancy) => {
  await withTransaction(['sales'], 'readwrite', (transaction) => {
    const store = transaction.objectStore('sales')
    const request = store.get(saleId)
    request.onsuccess = () => {
      if (!request.result) return
      store.put({
        ...request.result,
        status: 'synced',
        has_stock_discrepancy: Boolean(hasStockDiscrepancy),
        synced_at: new Date().toISOString(),
      })
    }
  })
}
