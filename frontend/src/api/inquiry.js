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

export const closeInquiryTask = (taskId, selectedLinkId = null) => {
  return api.post(`${INQUIRY_BASE}/tasks/${taskId}/close`, null, {
    params: selectedLinkId ? { selected_link_id: selectedLinkId } : {}
  })
}

export const syncErpRequisitions = (params = {}) => {
  return api.post('/erp/requisitions', null, {
    params
  })
}
