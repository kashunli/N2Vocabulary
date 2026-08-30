import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'io.github.kashunli.n2vocab',
  appName: 'N2 Vocabulary',
  webDir: '../static/react-rail',
  server: {
    url: 'https://words.kashunli.com/',
    cleartext: false
  }
};

export default config;
