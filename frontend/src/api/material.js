import request from './index'

const MATERIAL_BASE = '/material'

export const getMaterialList = (params = {}) => {
  return request.get(`${MATERIAL_BASE}/list`, { params })
}

export const getMaterialAnalysis = (material_code, params = {}) => {
  return request.get(`${MATERIAL_BASE}/analysis`, { params: { material_code, ...params } })
}
