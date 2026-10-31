// The studio bundle (static/mobile-studio.js): three.js, the studio's scene and the campus's places,
// loaded only when the studio is first drawn. The page calls
// window.AgentStudio.createStudioScene(stage, overlay, options, handlers, mode) and, for a place,
// window.AgentStudio.createPlaceScene(stage, overlay, options, AgentStudio.places[name], handlers).
import { buildCampus } from './places/campus'
import { buildDesk } from './places/desk'
import { buildDuty } from './places/duty'
import { buildLibrary } from './places/library'
import { buildSite } from './places/site'
import { createPlaceScene } from './places/stage'
import { createStudioScene } from './scene'

const places = { campus: buildCampus, library: buildLibrary, site: buildSite, duty: buildDuty, desk: buildDesk }

declare global {
  interface Window {
    AgentStudio?: { createStudioScene: typeof createStudioScene; createPlaceScene: typeof createPlaceScene; places: typeof places }
  }
}

window.AgentStudio = { createStudioScene, createPlaceScene, places }
