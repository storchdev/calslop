/**
 * Global app state for view mode, calendar sub-view, selected day, and focus.
 */
export type ViewMode = 'calendar' | 'todo';
export type CalendarView = 'day' | 'month';
export type CalendarDensity = 'minimal' | 'balanced' | 'dense';

class AppStore {
  viewMode = $state<ViewMode>('calendar');
  calendarView = $state<CalendarView>('month');
  calendarDensity = $state<CalendarDensity>('balanced');
  showTodosOnCalendar = $state<boolean>(true);
  selectedDate = $state<Date>(new Date(new Date().getFullYear(), new Date().getMonth(), new Date().getDate()));
  focusedEventIndex = $state<number>(-1);
  focusedTodoIndex = $state<number>(-1);
  focusedDayIndex = $state<number>(-1);
  modalOpen = $state<'event' | 'todo' | 'shortcuts' | null>(null);
  editingId = $state<string | null>(null);
  hasUnsyncedChanges = $state(false);
  /** IANA timezone (e.g. America/New_York) or empty string for browser local */
  timezone = $state<string>('');

  setViewMode(mode: ViewMode) {
    this.viewMode = mode;
  }

  setCalendarView(cv: CalendarView) {
    this.calendarView = cv;
  }

  setCalendarDensity(density: CalendarDensity) {
    this.calendarDensity = density;
  }

  cycleCalendarDensity() {
    const order: CalendarDensity[] = ['minimal', 'balanced', 'dense'];
    const i = order.indexOf(this.calendarDensity);
    this.calendarDensity = order[(i + 1) % order.length];
  }

  setShowTodosOnCalendar(show: boolean) {
    this.showTodosOnCalendar = show;
  }

  toggleShowTodosOnCalendar() {
    this.showTodosOnCalendar = !this.showTodosOnCalendar;
  }

  setSelectedDate(d: Date) {
    this.selectedDate = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  }

  goToToday() {
    this.setSelectedDate(new Date());
  }

  setFocusedEventIndex(i: number) {
    this.focusedEventIndex = i;
  }

  setFocusedTodoIndex(i: number) {
    this.focusedTodoIndex = i;
  }

  setFocusedDayIndex(i: number) {
    this.focusedDayIndex = i;
  }

  setModalOpen(m: 'event' | 'todo' | 'shortcuts' | null) {
    this.modalOpen = m;
  }

  setEditingId(id: string | null) {
    this.editingId = id;
  }

  setUnsyncedChanges(unsynced: boolean) {
    this.hasUnsyncedChanges = unsynced;
  }

  setTimezone(tz: string) {
    this.timezone = tz;
  }

  resetFocus() {
    this.focusedEventIndex = -1;
    this.focusedTodoIndex = -1;
    this.focusedDayIndex = -1;
  }
}

export const app = new AppStore();
