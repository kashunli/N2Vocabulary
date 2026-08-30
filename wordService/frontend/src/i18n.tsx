import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { normalizeLanguage, preferredTranslation, readStoredLanguage, LANGUAGE_STORAGE_KEY } from "./language.mjs";
import type { PlaybackRunMode } from "./features/player/playbackSettings";
import type { MarkStatus } from "./features/study/markStatus";
import type { FilterState } from "./features/study/studyTypes";

export type AppLanguage = "en" | "zh";

export interface LanguageCopy {
  documentTitle: string;
  brandCaption: string;
  studyWall: string;
  languageLabel: string;
  english: string;
  chinese: string;
  book: string;
  chooseBook: string;
  section: string;
  allSections: string;
  loadingSections: string;
  wordCount: (count: number) => string;
  filterItems: string;
  filterLabel: (filter: FilterState) => string;
  blurStudyContent: string;
  hideVocabularyList: string;
  showVocabularyList: string;
  openPlaybackSettings: string;
  playbackSettings: string;
  vocabularyPlaybackList: string;
  currentVocabularyItem: string;
  adjustPlaybackListWidth: string;
  loadingStudyState: string;
  loadingVocabulary: string;
  noWordsMatch: string;
  statusLabel: (status: MarkStatus) => string;
  reviewedLabel: string;
  statusSeparator: string;
  reviewed: (level: number, nextDate: string) => string;
  word: string;
  sentence: string;
  playWordAudio: (word: string) => string;
  playSentenceAudio: string;
  sentenceTranslation: string;
  sentenceExplanation: string;
  player: {
    controlsLabel: string;
    play: string;
    pause: string;
    previousAria: string;
    previousTitle: string;
    replayAria: string;
    replayTitle: string;
    nextAria: string;
    nextTitle: string;
    modeLabel: (mode: PlaybackRunMode) => string;
    modeDescription: (mode: PlaybackRunMode) => string;
    modeSwitchAria: (current: string, next: string) => string;
    modeSwitchTitle: (current: string, next: string) => string;
    defaultStatus: (mode: string) => string;
    nativeQueuePause: string;
    nativeQueuePaused: string;
    nativeBackgroundPlayer: string;
    markKnown: string;
    markFlagged: string;
    waveformPosition: string;
    waveformLoadFailed: string;
  };
  settings: {
    eyebrow: string;
    title: string;
    close: string;
    introduction: string;
    steps: (count: number, max: number) => string;
    sequenceSteps: string;
    audioElement: string;
    unavailableAudio: string;
    moveStep: (step: number) => string;
    moveStepUp: (step: number) => string;
    moveStepDown: (step: number) => string;
    repeat: string;
    decreaseRepeat: (step: number) => string;
    repeatCount: (step: number) => string;
    increaseRepeat: (step: number) => string;
    pauseAfter: string;
    pauseAfterStep: (step: number) => string;
    pauseAfterStepSeconds: (step: number) => string;
    remove: string;
    addStep: string;
    addWord: string;
    addSentence: string;
    listPlayback: string;
    resetSequence: string;
  };
  account: {
    logOut: string;
    signInOrRegister: string;
    signIn: string;
    createAccount: string;
    progressStored: string;
    email: string;
    password: string;
    working: string;
    register: string;
    needAccount: string;
    alreadyRegistered: string;
    cancel: string;
    guestProgressFound: string;
    chooseProgress: (email: string) => string;
    importGuestProgress: string;
    keepAccountProgress: string;
    cancelImport: string;
  };
  errors: {
    saveStudyPlayback: string;
    reviewCompletedElsewhere: string;
    saveReviewCompletion: string;
    loadBooks: string;
    loadSections: string;
    updateStudyMark: string;
    accountRequest: string;
    guestImport: string;
    audioPlayback: string;
  };
  markMessage: (word: string, status: MarkStatus) => string;
  reviewStatus: (word: string, level: number, nextDate: string) => string;
  formatDate: (value: string) => string;
}

const EN_COPY: LanguageCopy = {
  documentTitle: "N2 Study Wall",
  brandCaption: "JLPT N2 · VOCABULARY",
  studyWall: "Study Wall",
  languageLabel: "Language",
  english: "English",
  chinese: "中文",
  book: "Book",
  chooseBook: "Choose book",
  section: "Section",
  allSections: "All sections",
  loadingSections: "Loading sections…",
  wordCount: (count) => `${count} words`,
  filterItems: "Filter items",
  filterLabel: (filter) => ({all: "All", review: "Review", unmarked: "Unmarked", known: "Known", flagged: "Flagged"}[filter]),
  blurStudyContent: "B: blur / reveal the study content",
  hideVocabularyList: "Hide the vocabulary list",
  showVocabularyList: "Show the vocabulary list",
  openPlaybackSettings: "Open playback settings",
  playbackSettings: "Playback settings",
  vocabularyPlaybackList: "Vocabulary playback list",
  currentVocabularyItem: "Current vocabulary item",
  adjustPlaybackListWidth: "Adjust playback list width",
  loadingStudyState: "Loading study state…",
  loadingVocabulary: "Loading vocabulary…",
  noWordsMatch: "No words match the current filters.",
  statusLabel: (status) => ({unmarked: "", known: "Known", flagged: "Flagged"}[status]),
  reviewedLabel: "Reviewed",
  statusSeparator: ", ",
  reviewed: (level, nextDate) => `Reviewed · level ${level} · next ${nextDate}`,
  word: "Word",
  sentence: "Sentence",
  playWordAudio: (word) => `Play word audio: ${word}`,
  playSentenceAudio: "Play sentence audio",
  sentenceTranslation: "Sentence translation",
  sentenceExplanation: "Sentence explanation",
  player: {
    controlsLabel: "Playback controls",
    play: "Play",
    pause: "Pause",
    previousAria: "Play previous word or sentence",
    previousTitle: "Previous (A / ←)",
    replayAria: "Replay focused word or sentence",
    replayTitle: "Replay (R)",
    nextAria: "Play next word or sentence",
    nextTitle: "Next (D / →)",
    modeLabel: (mode) => ({single: "Single audio", list: "Play list once", "cycle-list": "Cycle this list", "next-list": "Continue to next list"}[mode]),
    modeDescription: (mode) => ({single: "Stop after the focused audio occurrence.", list: "Play every available row in this list once, then stop.", "cycle-list": "When this list ends, start it again from the beginning.", "next-list": "When this section ends, continue with the following section."}[mode]),
    modeSwitchAria: (current, next) => `Playback mode: ${current}. Switch to ${next}.`,
    modeSwitchTitle: (current, next) => `Playback mode: ${current}. Click to switch to ${next}.`,
    defaultStatus: (mode) => `${mode} · Click the wave to seek or play · Space to play/pause`,
    nativeQueuePause: "Native queue pause",
    nativeQueuePaused: "Native queue paused",
    nativeBackgroundPlayer: "Native background player",
    markKnown: "Mark as known",
    markFlagged: "Flag for review",
    waveformPosition: "Current line playback position",
    waveformLoadFailed: "The waveform could not be loaded. Seeking is still available.",
  },
  settings: {
    eyebrow: "PLAYBACK RECIPE",
    title: "Listening sequence",
    close: "Close playback settings",
    introduction: "Each row is one playback occurrence. Add the same audio more than once when you want it repeated later.",
    steps: (count, max) => `${count}/${max} steps`,
    sequenceSteps: "Listening sequence steps",
    audioElement: "Audio element",
    unavailableAudio: "Unavailable audio is skipped automatically.",
    moveStep: (step) => `Move step ${step}`,
    moveStepUp: (step) => `Move step ${step} up`,
    moveStepDown: (step) => `Move step ${step} down`,
    repeat: "Repeat",
    decreaseRepeat: (step) => `Decrease repeat for step ${step}`,
    repeatCount: (step) => `Repeat count for step ${step}`,
    increaseRepeat: (step) => `Increase repeat for step ${step}`,
    pauseAfter: "Pause after",
    pauseAfterStep: (step) => `Pause after step ${step}`,
    pauseAfterStepSeconds: (step) => `Pause after step ${step} in seconds`,
    remove: "Remove",
    addStep: "Add step",
    addWord: "+ Word",
    addSentence: "+ Sentence",
    listPlayback: "List playback",
    resetSequence: "Reset sequence",
  },
  account: {
    logOut: "Log out",
    signInOrRegister: "Sign in / Register",
    signIn: "Sign in",
    createAccount: "Create account",
    progressStored: "Account progress is stored in the separate local users database.",
    email: "Email",
    password: "Password",
    working: "Working…",
    register: "Register",
    needAccount: "Need an account? Register",
    alreadyRegistered: "Already registered? Sign in",
    cancel: "Cancel",
    guestProgressFound: "Guest progress found",
    chooseProgress: (email) => `Choose which progress should become active for ${email}. Study changes are paused until you decide.`,
    importGuestProgress: "Import guest progress",
    keepAccountProgress: "Keep account progress",
    cancelImport: "Cancel and remain logged out",
  },
  errors: {
    saveStudyPlayback: "Could not save study playback.",
    reviewCompletedElsewhere: "This review was already completed elsewhere. Re-enter Review to refresh the due list.",
    saveReviewCompletion: "Could not save review completion.",
    loadBooks: "Could not load books.",
    loadSections: "Could not load sections.",
    updateStudyMark: "Could not update the study mark.",
    accountRequest: "Account request failed.",
    guestImport: "Guest import failed.",
    audioPlayback: "Audio could not be played.",
  },
  markMessage: (word, status) => `${word} is ${status === "known" ? "known" : status === "flagged" ? "flagged" : "unmarked"}.`,
  reviewStatus: (word, level, nextDate) => `${word} reviewed. Level ${level}; next review ${nextDate}.`,
  formatDate: (value) => new Date(value).toLocaleDateString("en-US"),
};

const ZH_COPY: LanguageCopy = {
  documentTitle: "N2 学习墙",
  brandCaption: "JLPT N2 · 词汇",
  studyWall: "学习墙",
  languageLabel: "语言",
  english: "English",
  chinese: "中文",
  book: "词书",
  chooseBook: "选择词书",
  section: "单元",
  allSections: "全部单元",
  loadingSections: "正在加载单元…",
  wordCount: (count) => `${count} 个词`,
  filterItems: "筛选词汇",
  filterLabel: (filter) => ({all: "全部", review: "复习", unmarked: "未标记", known: "已掌握", flagged: "已标记"}[filter]),
  blurStudyContent: "B：模糊 / 显示学习内容",
  hideVocabularyList: "隐藏词汇列表",
  showVocabularyList: "显示词汇列表",
  openPlaybackSettings: "打开播放设置",
  playbackSettings: "播放设置",
  vocabularyPlaybackList: "词汇播放列表",
  currentVocabularyItem: "当前词汇",
  adjustPlaybackListWidth: "调整播放列表宽度",
  loadingStudyState: "正在加载学习状态…",
  loadingVocabulary: "正在加载词汇…",
  noWordsMatch: "没有符合当前筛选条件的词汇。",
  statusLabel: (status) => ({unmarked: "", known: "已掌握", flagged: "已标记"}[status]),
  reviewedLabel: "已复习",
  statusSeparator: "，",
  reviewed: (level, nextDate) => `已复习 · 等级 ${level} · 下次复习 ${nextDate}`,
  word: "单词",
  sentence: "句子",
  playWordAudio: (word) => `播放单词音频：${word}`,
  playSentenceAudio: "播放句子音频",
  sentenceTranslation: "句子翻译",
  sentenceExplanation: "句子讲解",
  player: {
    controlsLabel: "播放控制",
    play: "播放",
    pause: "暂停",
    previousAria: "播放上一个单词或句子",
    previousTitle: "上一个（A / ←）",
    replayAria: "重播当前单词或句子",
    replayTitle: "重播（R）",
    nextAria: "播放下一个单词或句子",
    nextTitle: "下一个（D / →）",
    modeLabel: (mode) => ({single: "单次播放", list: "播放列表一次", "cycle-list": "循环播放列表", "next-list": "继续下一个单元"}[mode]),
    modeDescription: (mode) => ({single: "播放当前音频后停止。", list: "播放此列表中所有可用行各一次，然后停止。", "cycle-list": "列表结束后从头开始。", "next-list": "本单元结束后继续下一个单元。"}[mode]),
    modeSwitchAria: (current, next) => `播放模式：当前为${current}。切换为${next}。`,
    modeSwitchTitle: (current, next) => `播放模式：当前为${current}。点击切换为${next}。`,
    defaultStatus: (mode) => `${mode} · 点击波形进行定位或播放 · 空格键播放/暂停`,
    nativeQueuePause: "原生播放队列暂停中",
    nativeQueuePaused: "原生播放队列已暂停",
    nativeBackgroundPlayer: "原生后台播放器",
    markKnown: "标记为已掌握",
    markFlagged: "标记待复习",
    waveformPosition: "当前行的播放位置",
    waveformLoadFailed: "波形加载失败，但仍可以进行定位。",
  },
  settings: {
    eyebrow: "播放方案",
    title: "听力播放序列",
    close: "关闭播放设置",
    introduction: "每一行代表一次播放。想稍后重复播放同一音频时，可以再次添加。",
    steps: (count, max) => `${count}/${max} 个步骤`,
    sequenceSteps: "听力播放步骤",
    audioElement: "音频内容",
    unavailableAudio: "没有音频时会自动跳过。",
    moveStep: (step) => `移动第 ${step} 步`,
    moveStepUp: (step) => `上移第 ${step} 步`,
    moveStepDown: (step) => `下移第 ${step} 步`,
    repeat: "重复",
    decreaseRepeat: (step) => `减少第 ${step} 步的重复次数`,
    repeatCount: (step) => `第 ${step} 步的重复次数`,
    increaseRepeat: (step) => `增加第 ${step} 步的重复次数`,
    pauseAfter: "播放后暂停",
    pauseAfterStep: (step) => `第 ${step} 步播放后暂停`,
    pauseAfterStepSeconds: (step) => `第 ${step} 步播放后暂停的秒数`,
    remove: "移除",
    addStep: "添加步骤",
    addWord: "+ 单词",
    addSentence: "+ 句子",
    listPlayback: "列表播放",
    resetSequence: "重置播放序列",
  },
  account: {
    logOut: "退出登录",
    signInOrRegister: "登录 / 注册",
    signIn: "登录",
    createAccount: "创建账户",
    progressStored: "账户进度保存在单独的本地用户数据库中。",
    email: "邮箱",
    password: "密码",
    working: "处理中…",
    register: "注册",
    needAccount: "还没有账户？注册",
    alreadyRegistered: "已经注册？登录",
    cancel: "取消",
    guestProgressFound: "发现访客进度",
    chooseProgress: (email) => `选择要为 ${email} 启用的进度。在作出选择前，学习操作会暂停。`,
    importGuestProgress: "导入访客进度",
    keepAccountProgress: "保留账户进度",
    cancelImport: "取消并保持退出登录",
  },
  errors: {
    saveStudyPlayback: "无法保存学习记录。",
    reviewCompletedElsewhere: "此复习已在其他位置完成。请重新进入“复习”以刷新待复习列表。",
    saveReviewCompletion: "无法保存复习完成记录。",
    loadBooks: "无法加载词书。",
    loadSections: "无法加载单元。",
    updateStudyMark: "无法更新学习标记。",
    accountRequest: "账户请求失败。",
    guestImport: "访客进度导入失败。",
    audioPlayback: "音频播放失败。",
  },
  markMessage: (word, status) => `${word}：${status === "known" ? "已掌握" : status === "flagged" ? "已标记" : "已取消标记"}。`,
  reviewStatus: (word, level, nextDate) => `${word}：已复习。等级 ${level}；下次复习 ${nextDate}。`,
  formatDate: (value) => new Date(value).toLocaleDateString("zh-CN"),
};

const KNOWN_ERROR_TRANSLATIONS: Record<string, string> = {
  "Choose how to handle guest progress before studying.": "请先选择如何处理访客进度，然后再开始学习。",
  "Could not update the study mark.": ZH_COPY.errors.updateStudyMark,
  "Could not save study playback.": ZH_COPY.errors.saveStudyPlayback,
  "Could not save review completion.": ZH_COPY.errors.saveReviewCompletion,
  "Could not load books.": ZH_COPY.errors.loadBooks,
  "Could not load sections.": ZH_COPY.errors.loadSections,
  "Account request failed.": ZH_COPY.errors.accountRequest,
  "Guest import failed.": ZH_COPY.errors.guestImport,
  "Audio could not be played.": ZH_COPY.errors.audioPlayback,
  "Native audio playback is unavailable.": "原生音频播放不可用。",
};

interface LanguageContextValue {
  language: AppLanguage;
  setLanguage: (language: AppLanguage) => void;
  copy: LanguageCopy;
  selectText: (english?: string, chinese?: string) => string;
  localizeMessage: (message: string) => string;
}

const LanguageContext = createContext<LanguageContextValue | undefined>(undefined);

export function LanguageProvider({children}: {children: ReactNode}) {
  const [language, setLanguageState] = useState<AppLanguage>(() => {
    if (typeof window === "undefined") return "en";
    try {
      return readStoredLanguage(window.localStorage) as AppLanguage;
    } catch {
      return "en";
    }
  });
  const copy = language === "zh" ? ZH_COPY : EN_COPY;

  const setLanguage = useCallback((nextLanguage: AppLanguage) => {
    setLanguageState(normalizeLanguage(nextLanguage) as AppLanguage);
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
    } catch {
      // A private browsing context can reject localStorage. The current tab
      // still keeps the selected language in React state.
    }
    document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
    document.title = copy.documentTitle;
  }, [copy.documentTitle, language]);

  useEffect(() => {
    const handleStorage = (event: StorageEvent) => {
      if (event.key === LANGUAGE_STORAGE_KEY) {
        setLanguageState(normalizeLanguage(event.newValue) as AppLanguage);
      }
    };
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  const selectText = useCallback((english?: string, chinese?: string) => preferredTranslation(language, english, chinese), [language]);
  const localizeMessage = useCallback((message: string) => language === "zh" ? KNOWN_ERROR_TRANSLATIONS[message] || message : message, [language]);
  const value = useMemo<LanguageContextValue>(() => ({language, setLanguage, copy, selectText, localizeMessage}), [copy, language, localizeMessage, selectText, setLanguage]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useI18n() {
  const value = useContext(LanguageContext);
  if (!value) throw new Error("useI18n must be used inside LanguageProvider");
  return value;
}
