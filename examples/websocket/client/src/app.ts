/**
 * Enhanced Pipecat Client Implementation with Preemptive Response Logging
 *
 * This client connects to an RTVI-compatible bot server and handles
 * preemptive response logging events from the server.
 */

import {
  PipecatClient,
  PipecatClientOptions,
  RTVIEvent,
} from '@pipecat-ai/client-js';
import { WebSocketTransport } from '@pipecat-ai/websocket-transport';

interface PreemptiveLogData {
  type: 'preemptive_log';
  event: string;
  timestamp: number;
  data: {
    message: string;
    [key: string]: any;
  };
}

class WebsocketClientApp {
  private pcClient: PipecatClient | null = null;
  private connectBtn: HTMLButtonElement | null = null;
  private disconnectBtn: HTMLButtonElement | null = null;
  private statusSpan: HTMLElement | null = null;
  private debugLog: HTMLElement | null = null;
  private preemptiveLog: HTMLElement | null = null;
  private botAudio: HTMLAudioElement;

  constructor() {
    console.log('WebsocketClientApp');
    this.botAudio = document.createElement('audio');
    this.botAudio.autoplay = true;
    document.body.appendChild(this.botAudio);

    this.setupDOMElements();
    this.setupEventListeners();
  }

  /**
   * Set up references to DOM elements and create necessary media elements
   */
  private setupDOMElements(): void {
    this.connectBtn = document.getElementById(
      'connect-btn'
    ) as HTMLButtonElement;
    this.disconnectBtn = document.getElementById(
      'disconnect-btn'
    ) as HTMLButtonElement;
    this.statusSpan = document.getElementById('connection-status');
    this.debugLog = document.getElementById('debug-log');
    this.preemptiveLog = document.getElementById('preemptive-log');
    
    // Create preemptive log container if it doesn't exist
    if (!this.preemptiveLog) {
      this.preemptiveLog = document.createElement('div');
      this.preemptiveLog.id = 'preemptive-log';
      this.preemptiveLog.innerHTML = '<h3>Preemptive Response Log</h3>';
      this.preemptiveLog.style.cssText = `
        border: 1px solid #ccc;
        padding: 10px;
        margin: 10px 0;
        max-height: 300px;
        overflow-y: auto;
        background-color: #f9f9f9;
      `;
      document.body.appendChild(this.preemptiveLog);
    }
  }

  /**
   * Set up event listeners for connect/disconnect buttons
   */
  private setupEventListeners(): void {
    this.connectBtn?.addEventListener('click', () => this.connect());
    this.disconnectBtn?.addEventListener('click', () => this.disconnect());
  }

  /**
   * Add a timestamped message to the debug log
   */
  private log(message: string): void {
    if (!this.debugLog) return;
    const entry = document.createElement('div');
    entry.textContent = `${new Date().toISOString()} - ${message}`;
    if (message.startsWith('User: ')) {
      entry.style.color = '#2196F3';
    } else if (message.startsWith('Bot: ')) {
      entry.style.color = '#4CAF50';
    } else if (message.startsWith('Assistant: ')) {
      entry.style.color = '#FF9800'; // Red for errors
    }
    this.debugLog.appendChild(entry);
    this.debugLog.scrollTop = this.debugLog.scrollHeight;
    console.log(message);
  }

  /**
   * Add a preemptive response log entry
   */
  private logPreemptive(eventType: string, data: any): void {
    if (!this.preemptiveLog) return;
    
    const entry = document.createElement('div');
    entry.style.cssText = `
      margin: 5px 0;
      padding: 8px;
      border-left: 3px solid ${this.getEventColor(eventType)};
      background-color: white;
      font-family: monospace;
      font-size: 12px;
    `;
    
    const timestamp = new Date(data.timestamp * 1000).toLocaleTimeString();
    const message = data.data?.message || 'No message';
    
    let details = '';
    if (data.data) {
      const filteredData = { ...data.data };
      delete filteredData.message; // Remove message as it's already shown
      
      if (Object.keys(filteredData).length > 0) {
        details = `<div style="margin-top: 4px; color: #666;">
          ${JSON.stringify(filteredData, null, 2)}
        </div>`;
      }
    }
    
    entry.innerHTML = `
      <div style="font-weight: bold; color: ${this.getEventColor(eventType)};">
        [${timestamp}] ${eventType.toUpperCase()}
      </div>
      <div>${message}</div>
      ${details}
    `;
    
    this.preemptiveLog.appendChild(entry);
    this.preemptiveLog.scrollTop = this.preemptiveLog.scrollHeight;
    
    // Keep only last 50 entries to prevent memory issues
    const entries = this.preemptiveLog.querySelectorAll('div:not(h3)');
    // if (entries.length > 50) {
    //   entries[0].remove();
    // }
  }

  /**
   * Get color for different event types
   */
  private getEventColor(eventType: string): string {
    const colors: { [key: string]: string } = {
      'timer_started': '#2196F3',
      'timer_cancelled': '#FF9800',
      'triggered': '#4CAF50',
      'generated': '#8BC34A',
      'tts_started': '#9C27B0',
      'tts_stopped': '#673AB7',
      'error': '#F44336',
      'timer_error': '#F44336'
    };
    return colors[eventType] || '#666';
  }

  /**
   * Update the connection status display
   */
  private updateStatus(status: string): void {
    if (this.statusSpan) {
      this.statusSpan.textContent = status;
    }
    this.log(`Status: ${status}`);
  }

  /**
   * Handle server messages, including preemptive logging
   */
  private handleServerMessage(data: any): void {
    if (data?.type === 'preemptive_log') {
      const message = data.data?.message || 'No message';
      this.logPreemptive(data.event, data);
      const filteredData = { ...data.data };
      delete filteredData.message;
      if (Object.keys(filteredData).length > 0) {
        if(filteredData.text)
        this.log(`Assistant: ${filteredData.text}`);
      }
    } 
    // else {
    //   this.log(`Server message: ${JSON.stringify(data)}`);
    // }
  }

  /**
   * Check for available media tracks and set them up if present
   */
  setupMediaTracks() {
    if (!this.pcClient) return;
    const tracks = this.pcClient.tracks();
    if (tracks.bot?.audio) {
      this.setupAudioTrack(tracks.bot.audio);
    }
  }

  /**
   * Set up listeners for track events (start/stop)
   */
  setupTrackListeners() {
    if (!this.pcClient) return;

    this.pcClient.on(RTVIEvent.TrackStarted, (track, participant) => {
      if (!participant?.local && track.kind === 'audio') {
        this.setupAudioTrack(track);
      }
    });

    this.pcClient.on(RTVIEvent.TrackStopped, (track, participant) => {
      this.log(
        `Track stopped: ${track.kind} from ${participant?.name || 'unknown'}`
      );
    });
  }

  /**
   * Set up an audio track for playback
   */
  private setupAudioTrack(track: MediaStreamTrack): void {
    this.log('Setting up audio track');
    if (
      this.botAudio.srcObject &&
      'getAudioTracks' in this.botAudio.srcObject
    ) {
      const oldTrack = this.botAudio.srcObject.getAudioTracks()[0];
      if (oldTrack?.id === track.id) return;
    }
    this.botAudio.srcObject = new MediaStream([track]);
  }

  /**
   * Initialize and connect to the bot
   */
  public async connect(): Promise<void> {
    try {
      const startTime = Date.now();

      const PipecatConfig: PipecatClientOptions = {
        transport: new WebSocketTransport(),
        enableMic: true,
        enableCam: false,
        callbacks: {
          onConnected: () => {
            this.updateStatus('Connected');
            if (this.connectBtn) this.connectBtn.disabled = true;
            if (this.disconnectBtn) this.disconnectBtn.disabled = false;
          },
          onDisconnected: () => {
            this.updateStatus('Disconnected');
            if (this.connectBtn) this.connectBtn.disabled = false;
            if (this.disconnectBtn) this.disconnectBtn.disabled = true;
            this.log('Client disconnected');
          },
          onBotReady: (data) => {
            this.log(`Bot ready: ${JSON.stringify(data)}`);
            this.setupMediaTracks();
          },
          onUserTranscript: (data) => {
            if (data.final) {
              this.log(`User: ${data.text}`);
            }
          },
          onBotTranscript: (data) => this.log(`Bot: ${data.text}`),
          onServerMessage: (data) => this.handleServerMessage(data),
          onMessageError: (error) => console.error('Message error:', error),
          onError: (error) => console.error('Error:', error),
        },
      };  
      this.pcClient = new PipecatClient(PipecatConfig);
      // @ts-ignore
      window.pcClient = this.pcClient; // Expose for debugging
      this.setupTrackListeners();

      this.log('Initializing devices...');
      await this.pcClient.initDevices();

      this.log('Connecting to bot...');
      await this.pcClient.connect({
        endpoint: 'http://localhost:7860/connect',
      });

      const timeTaken = Date.now() - startTime;
      this.log(`Connection complete, timeTaken: ${timeTaken}`);
    } catch (error) {
      this.log(`Error connecting: ${(error as Error).message}`);
      this.updateStatus('Error');
      if (this.pcClient) {
        try {
          await this.pcClient.disconnect();
        } catch (disconnectError) {
          this.log(`Error during disconnect: ${disconnectError}`);
        }
      }
    }
  }

  /**
   * Disconnect from the bot and clean up media resources
   */
  public async disconnect(): Promise<void> {
    if (this.pcClient) {
      try {
        await this.pcClient.disconnect();
        this.pcClient = null;
        if (
          this.botAudio.srcObject &&
          'getAudioTracks' in this.botAudio.srcObject
        ) {
          this.botAudio.srcObject
            .getAudioTracks()
            .forEach((track) => track.stop());
          this.botAudio.srcObject = null;
        }
      } catch (error) {
        this.log(`Error disconnecting: ${(error as Error).message}`);
      }
    }
  }
}

declare global {
  interface Window {
    WebsocketClientApp: typeof WebsocketClientApp;
  }
}

window.addEventListener('DOMContentLoaded', () => {
  window.WebsocketClientApp = WebsocketClientApp;
  new WebsocketClientApp();
});