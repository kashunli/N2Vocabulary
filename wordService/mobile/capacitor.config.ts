import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'io.github.kashunli.n2vocab',
  appName: 'N2 Vocabulary',
  webDir: '../static/react-rail',
  server: {
    url: 'https://joeswords.weneednowall.monster/',
    cleartext: false
  }
};

export default config;
