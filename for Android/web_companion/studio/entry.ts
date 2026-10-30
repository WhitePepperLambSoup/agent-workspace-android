// The studio bundle (static/mobile-studio.js): three.js and the scene, loaded only when the studio
// opens. The page calls window.AgentStudio.createStudioScene(stage, overlay, options, handlers).
import { createStudioScene } from './scene'

declare global {
  interface Window {
    AgentStudio?: { createStudioScene: typeof createStudioScene }
  }
}

window.AgentStudio = { createStudioScene }
