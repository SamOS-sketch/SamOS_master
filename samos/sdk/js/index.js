
const axios = require('axios');

class SamOSClient {
  constructor({ baseUrl = 'http://localhost:8000' } = {}) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.http = axios.create({ baseURL: this.baseUrl, timeout: 30000 });
  }

  async startSession() {
    const { data } = await this.http.post('/session/start');
    return data;
  }

  async getMode(sessionId) {
    const { data } = await this.http.get('/session/mode', { params: { session_id: sessionId } });
    return data;
  }

  async setMode(sessionId, mode) {
    const { data } = await this.http.post('/session/mode', { session_id: sessionId, mode });
    return data;
  }

  async putMemory(sessionId, key, value, meta = {}) {
    const { data } = await this.http.post('/memory', { session_id: sessionId, key, value, meta });
    return data;
  }

  async getMemory(sessionId, key) {
    const { data } = await this.http.get('/memory', { params: { session_id: sessionId, key } });
    return data;
  }

  async listMemory(sessionId) {
    const { data } = await this.http.get('/memory/list', { params: { session_id: sessionId } });
    return data;
  }

  async createEmm(sessionId, type, message = null, meta = {}) {
    const { data } = await this.http.post('/emm', { session_id: sessionId, type, message, meta });
    return data;
  }

  async listEmms(sessionId, limit = 50) {
    const { data } = await this.http.get('/emm/list', { params: { session_id: sessionId, limit } });
    return data;
  }

  async exportEmms(sessionId) {
    const { data } = await this.http.get('/emm/export', { params: { session_id: sessionId } });
    return data;
  }

  async generateImage(sessionId, prompt) {
    try {
      const { data } = await this.http.post('/image/generate', { session_id: sessionId, prompt });
      return data;
    } catch (err) {
      const detail = err.response?.data?.detail || err.message;
      throw new Error(`Image generation failed: ${detail}`);
    }
  }
}

module.exports = { SamOSClient };
