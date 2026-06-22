import api from './index'

const AGENT_BASE = '/agent'

export const getProcurementAgentStatus = () => {
  return api.get(`${AGENT_BASE}/status`)
}

export const createProcurementAgentSession = () => {
  return api.post(`${AGENT_BASE}/sessions`)
}

export const getProcurementAgentSessions = () => {
  return api.get(`${AGENT_BASE}/sessions`)
}

export const getProcurementAgentSessionMessages = (sessionId) => {
  return api.get(`${AGENT_BASE}/sessions/${sessionId}/messages`)
}

export const sendProcurementAgentMessage = (payload) => {
  return api.post(`${AGENT_BASE}/chat`, payload)
}

export const clearProcurementAgentMemory = (payload) => {
  return api.post(`${AGENT_BASE}/memory/clear`, payload)
}
