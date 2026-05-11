import api from './index'

const INQUIRY_BASE = '/inquiry'



export const createInquiryTask = (data) => {
  return api.post(`${INQUIRY_BASE}/tasks`, data)
}

export const getInquiryTasks = (params = {}) => {
  return api.get(`${INQUIRY_BASE}/tasks`, { params })
}

export const updateTaskStatus = (taskId, status) => {
  return api.put(`${INQUIRY_BASE}/tasks/${taskId}/status`, null, { params: { status } })
}

export const addSupplierToTask = (taskId, supplierData) => {
  return api.post(`${INQUIRY_BASE}/tasks/${taskId}/suppliers`, null, {
    params: supplierData
  })
}

export const getTaskDetails = (taskId) => {
  return api.get(`${INQUIRY_BASE}/tasks/${taskId}/details`)
}

export const closeInquiryTask = (taskId, closeData = null) => {
  if (typeof closeData === 'number' || closeData === null) {
    return api.post(`${INQUIRY_BASE}/tasks/${taskId}/close`, null, {
      params: closeData ? { selected_link_id: closeData } : {}
    })
  }

  return api.post(`${INQUIRY_BASE}/tasks/${taskId}/close`, closeData)
}

export const saveManualQuotes = (taskId, data) => {
  return api.post(`${INQUIRY_BASE}/tasks/${taskId}/save-manual-quotes`, data)
}

export const saveCompareDraft = (taskId, data) => {
  return api.post(`${INQUIRY_BASE}/tasks/${taskId}/compare-draft`, data)
}

export const getCompareDrafts = () => {
  return api.get(`${INQUIRY_BASE}/compare-drafts`)
}

export const deleteCompareDraft = (draftId) => {
  return api.delete(`${INQUIRY_BASE}/compare-drafts/${draftId}`)
}

export const deleteCompareDraftsByTask = (taskId) => {
  return api.delete(`${INQUIRY_BASE}/compare-drafts/by-task/${taskId}`)
}

export const syncErpRequisitions = (params = {}) => {
  return api.post('/erp/requisitions', null, {
    params
  })
}
