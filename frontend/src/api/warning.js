import api from './index'

export const getWarningDashboard = () => {
  return api.get('/warning/dashboard')
}

export const sendWarningToSupplier = (data) => {
  return api.post('/warning/send', data)
}

export const getMyWarningMessages = () => {
  return api.get('/warning/my-messages')
}

export const markWarningMessageRead = (messageId, data) => {
  return api.put(`/warning/my-messages/${messageId}/read`, data)
}

export const getSentWarningMessages = () => {
  return api.get('/warning/sent-messages')
}
