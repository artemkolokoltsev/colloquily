import 'i18next';
import { en } from './i18n';
declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'translation';
    returnNull: false;
    resources: { translation: typeof en.translation };
  }
}
