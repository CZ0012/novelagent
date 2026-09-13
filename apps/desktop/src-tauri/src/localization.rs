use serde::Deserialize;
use std::{
    collections::HashMap,
    sync::{
        atomic::{AtomicU8, Ordering},
        OnceLock,
    },
};

static ACTIVE_LOCALE: AtomicU8 = AtomicU8::new(0);
static ZH_CN: OnceLock<NativeLabels> = OnceLock::new();
static EN_US: OnceLock<NativeLabels> = OnceLock::new();

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NativeLocale {
    ZhCn,
    EnUs,
}

#[derive(Debug, Deserialize)]
pub struct NativeLabels {
    pub window_title: String,
    pub tray_tooltip: String,
    pub show_menu: String,
    pub quit_menu: String,
    messages: HashMap<String, String>,
}

impl NativeLocale {
    pub fn parse(locale: &str) -> Result<Self, String> {
        match locale {
            "zh-CN" => Ok(Self::ZhCn),
            "en-US" => Ok(Self::EnUs),
            _ => Err(native_message("unsupported_locale", &[("locale", locale)])),
        }
    }

    pub fn activate(self) {
        ACTIVE_LOCALE.store(if self == Self::EnUs { 1 } else { 0 }, Ordering::Relaxed);
    }

    pub fn labels(self) -> &'static NativeLabels {
        let (cache, source) = match self {
            Self::ZhCn => (&ZH_CN, include_str!("../localization/zh-CN.json")),
            Self::EnUs => (&EN_US, include_str!("../localization/en-US.json")),
        };
        cache.get_or_init(|| serde_json::from_str(source).expect("Invalid bundled native locale"))
    }

    fn message(self, key: &str, values: &[(&str, &str)]) -> String {
        let template = self
            .labels()
            .messages
            .get(key)
            .map(String::as_str)
            .unwrap_or(key);
        // Substitute once so user paths containing braces remain verbatim.
        let mut result = String::new();
        let mut rest = template;
        while let Some(start) = rest.find('{') {
            result.push_str(&rest[..start]);
            rest = &rest[start..];
            let Some(end) = rest.find('}') else { break };
            let name = &rest[1..end];
            result.push_str(
                values
                    .iter()
                    .find(|(key, _)| *key == name)
                    .map(|(_, value)| *value)
                    .unwrap_or(&rest[..=end]),
            );
            rest = &rest[end + 1..];
        }
        result.push_str(rest);
        result
    }
}

pub fn native_message(key: &str, values: &[(&str, &str)]) -> String {
    let locale = if ACTIVE_LOCALE.load(Ordering::Relaxed) == 1 {
        NativeLocale::EnUs
    } else {
        NativeLocale::ZhCn
    };
    locale.message(key, values)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn native_catalogs_have_identical_keys_and_placeholders() {
        let zh = NativeLocale::ZhCn.labels();
        let en = NativeLocale::EnUs.labels();
        assert_eq!(zh.messages.len(), en.messages.len());
        for (key, value) in &zh.messages {
            let translated = en.messages.get(key).expect("Missing native translation");
            assert!(!translated.trim().is_empty());
            let placeholders = |text: &str| {
                text.split('{')
                    .skip(1)
                    .filter_map(|part| part.split_once('}').map(|(name, _)| name.to_string()))
                    .collect::<std::collections::BTreeSet<_>>()
            };
            assert_eq!(placeholders(value), placeholders(translated), "{key}");
        }
        let result = NativeLocale::EnUs.message(
            "workspace_mismatch",
            &[
                ("backend_url", "http://localhost:8000"),
                ("actual", "D:\\{backend_url}\\novel"),
                ("expected_workspace_path", "D:\\writing"),
            ],
        );
        assert!(result.contains("D:\\{backend_url}\\novel"));
        assert!(result.contains("D:\\writing"));
    }
}
