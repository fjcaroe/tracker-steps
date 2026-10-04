import type { ModuleProps } from '../registry';
import TrackerModule from './TrackerModule';

/** Adaptador del módulo Tracker: conserva su login, su API y sus datos locales sin cambios de formato. */
export default function TrackerEntry({ onExit }: ModuleProps) { return <TrackerModule onExit={onExit} />; }
