import request from './index'

const MATERIAL_BASE = '/material'

export const getMaterialList = () => {
  return request.get(`${MATERIAL_BASE}/list`)
}

export const getMaterialAnalysis = (material_name) => {
  return request.get(`${MATERIAL_BASE}/analysis`, { params: { material_name } })
}
