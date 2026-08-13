//! Small deterministic review scheduler shared by account-backed study state.
//!
//! This is intentionally a fixed ladder, not SM-2 or FSRS. Keeping every
//! interval explicit makes the learner contract easy to audit and lets the
//! browser implementation use the same test vectors.

use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};

pub const INITIAL_INTERVAL: Duration = Duration::days(1);
pub const AGAIN_INTERVAL: Duration = Duration::minutes(10);
pub const HARD_INTERVAL: Duration = Duration::days(1);
const GOOD_DAYS: [i64; 6] = [1, 3, 7, 14, 30, 60];

#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Eq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum ReviewGrade {
    Again,
    Hard,
    Good,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ScheduleResult {
    pub good_step: u8,
    pub due_at: DateTime<Utc>,
    pub set_known: bool,
    pub set_flagged: bool,
}

pub fn initial_due_at(completed_at: DateTime<Utc>) -> DateTime<Utc> {
    completed_at + INITIAL_INTERVAL
}

pub fn schedule_review(
    current_good_step: u8,
    grade: ReviewGrade,
    reviewed_at: DateTime<Utc>,
) -> ScheduleResult {
    match grade {
        ReviewGrade::Again => ScheduleResult {
            good_step: 0,
            due_at: reviewed_at + AGAIN_INTERVAL,
            set_known: false,
            set_flagged: false,
        },
        ReviewGrade::Hard => ScheduleResult {
            good_step: current_good_step.min(6),
            due_at: reviewed_at + HARD_INTERVAL,
            set_known: false,
            set_flagged: true,
        },
        ReviewGrade::Good => {
            let next_step = current_good_step.saturating_add(1).clamp(1, 6);
            ScheduleResult {
                good_step: next_step,
                due_at: reviewed_at + Duration::days(GOOD_DAYS[usize::from(next_step - 1)]),
                set_known: true,
                set_flagged: false,
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn instant() -> DateTime<Utc> {
        "2026-08-13T00:00:00Z".parse().unwrap()
    }

    #[test]
    fn new_cards_start_one_day_after_complete_playback() {
        assert_eq!(initial_due_at(instant()), instant() + Duration::days(1));
    }

    #[test]
    fn again_and_hard_follow_the_fixed_contract() {
        let again = schedule_review(4, ReviewGrade::Again, instant());
        assert_eq!(again.good_step, 0);
        assert_eq!(again.due_at, instant() + Duration::minutes(10));
        assert!(!again.set_known && !again.set_flagged);

        let hard = schedule_review(4, ReviewGrade::Hard, instant());
        assert_eq!(hard.good_step, 4);
        assert_eq!(hard.due_at, instant() + Duration::days(1));
        assert!(hard.set_flagged && !hard.set_known);
    }

    #[test]
    fn good_uses_the_gentle_ladder_and_caps_at_sixty_days() {
        let expected = [1, 3, 7, 14, 30, 60, 60];
        for (step, days) in expected.into_iter().enumerate() {
            let result = schedule_review(step as u8, ReviewGrade::Good, instant());
            assert_eq!(result.good_step, ((step + 1).min(6)) as u8);
            assert_eq!(result.due_at, instant() + Duration::days(days));
            assert!(result.set_known && !result.set_flagged);
        }
    }
}
