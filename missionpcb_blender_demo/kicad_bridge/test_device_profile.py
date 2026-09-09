"""Prompt interpretation must preserve uncertainty before native CAD generation."""
import math
import unittest
from pathlib import Path

import device_profile as profile


class DeviceProfileTests(unittest.TestCase):
    def test_canonical_brief_preserves_adhesive_and_fourteen_days(self):
        brief = (Path(__file__).resolve().parents[2] / 'missions/ecg-patch.md').read_text()
        result = profile.extract_profile(brief)
        self.assertEqual(result['device_kind'], 'ecg')
        self.assertEqual(result['mount'], 'chest')
        self.assertEqual(result['attachment'], 'adhesive')
        self.assertEqual(result['interior_mm'], {'length': 100., 'width': 40., 'height': 7.})
        self.assertEqual(result['required_wear_hours'], 336.)
        self.assertEqual(result['status'], 'proposed')
        for matches in result['evidence'].values():
            for evidence in matches:
                self.assertEqual(brief[evidence['start']:evidence['end']], evidence['quote'])

    def test_eeg_headstrap_is_not_ecg_chest(self):
        result = profile.extract_profile('EEG headset on the head with a strap. '
                                       'Interior dimensions: 6 x 4 x 1 cm. Worn for 8 hours.')
        self.assertEqual((result['device_kind'], result['mount'], result['attachment']),
                         ('eeg', 'head', 'strap'))
        self.assertEqual(result['interior_mm'], {'length': 60., 'width': 40., 'height': 10.})
        self.assertEqual(result['required_wear_hours'], 8.)

    def test_generic_prompt_does_not_invent_an_ecg_or_housing(self):
        result = profile.extract_profile('Build a temperature monitor.')
        self.assertEqual(result['device_kind'], 'general')
        self.assertEqual(result['mount'], 'unspecified')
        self.assertEqual(result['attachment'], 'unspecified')
        self.assertIsNone(result['interior_mm'])
        self.assertIsNone(result['required_wear_hours'])
        self.assertTrue(result['unresolved'])

    def test_belt_is_explicit_strap_option(self):
        result = profile.extract_profile('ECG housing tied around the chest with a belt.')
        self.assertEqual(result['attachment'], 'strap')
        self.assertEqual(result['evidence']['attachment'][0]['quote'].lower(), 'belt')

    def test_ecg_alone_does_not_assume_chest(self):
        self.assertEqual(profile.extract_profile('ECG recorder')['mount'], 'unspecified')

    def test_ambiguous_prompts_remain_unresolved(self):
        result = profile.extract_profile('ECG or EEG, on the chest or wrist, using adhesive or a strap. '
                                       'Interior 100 x 40 x 7 mm or 80 x 40 x 9 mm. '
                                       'Worn for 7 or 14 days.')
        self.assertEqual(result['device_kind'], 'general')
        self.assertEqual(result['mount'], 'unspecified')
        self.assertEqual(result['attachment'], 'unspecified')
        self.assertIsNone(result['interior_mm'])
        self.assertIsNone(result['required_wear_hours'])

    def test_range_is_not_silently_reduced_to_a_single_duration(self):
        for duration in ['7–14 days', '7 to 14 days', '7-14 days', '7 or 14 days']:
            with self.subTest(duration=duration):
                self.assertIsNone(profile.extract_profile('Worn for ' + duration)['required_wear_hours'])

    def test_negated_alternatives_do_not_choose_wrong_model(self):
        result = profile.extract_profile('Not an ECG chest strap; use an EEG head device with adhesive.')
        self.assertEqual((result['device_kind'], result['mount'], result['attachment']),
                         ('eeg', 'head', 'adhesive'))

    def test_adhesive_free_is_not_adhesive_attachment(self):
        result = profile.extract_profile('An adhesive-free ECG chest device held by a belt.')
        self.assertEqual(result['attachment'], 'strap')

    def test_examples_do_not_become_the_selected_device(self):
        result = profile.extract_profile('Build a wearable, for example an ECG chest device with adhesive.')
        self.assertEqual(result['device_kind'], 'general')
        self.assertEqual(result['mount'], 'unspecified')
        self.assertEqual(result['attachment'], 'unspecified')

    def test_pcb_or_exterior_size_is_not_housing_interior(self):
        for text in ['PCB size 80 x 30 x 1.6 mm.', 'Housing exterior 100 x 40 x 7 mm.',
                     'Interior should be roomy. PCB 80 x 30 x 1.6 mm.']:
            with self.subTest(text=text):
                self.assertIsNone(profile.extract_profile(text)['interior_mm'])

    def test_battery_life_does_not_establish_wear_duration(self):
        result = profile.extract_profile('Chest ECG with 14 days of battery life. Wear comfortably.')
        self.assertIsNone(result['required_wear_hours'])

    def test_duration_words_and_maximum_target(self):
        result = profile.extract_profile('Worn continuously for up to two weeks.')
        self.assertEqual(result['required_wear_hours'], 336.)
        self.assertTrue(any('maximum' in item for item in result['assumptions']))

    def test_identical_repeated_dimensions_are_not_conflicting(self):
        result = profile.extract_profile('Interior 100 x 40 x 7 mm. Internal dimensions 10 x 4 x 0.7 cm.')
        self.assertEqual(result['interior_mm'], {'length': 100., 'width': 40., 'height': 7.})

    def test_explicit_reviewed_override_changes_only_supplied_geometry(self):
        source = profile.extract_profile('ECG chest patch with adhesive.')
        source['attachment'] = 'strap'
        result = profile.validate_profile(source)
        self.assertEqual(result['attachment'], 'strap')
        self.assertEqual(result['device_kind'], 'ecg')
        self.assertNotIn('evidence', result)

    def test_validation_rejects_nonfinite_boolean_and_out_of_range_dimensions(self):
        for value in [math.inf, -math.inf, math.nan, True, 0, -1, 2001, '10']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                profile.validate_profile({'interior_mm': {'length': value, 'width': 40, 'height': 7}})

    def test_validation_rejects_bad_duration_and_unknown_enums(self):
        for data in [{'required_wear_hours': math.nan}, {'required_wear_hours': 0},
                     {'required_wear_hours': True}, {'required_wear_hours': 87601},
                     {'mount': 'brain_implant'}, {'attachment': 'bolts'}, {'device_kind': 'fake'}]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                profile.validate_profile(data)

    def test_validation_rejects_misspelled_keys_and_partial_dimensions(self):
        for data in [{'interior_m': [100, 40, 7]}, {'interior_mm': {'length': 100, 'width': 40}}]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                profile.validate_profile(data)

    def test_invalid_explicit_dimensions_are_unresolved_instead_of_crashing(self):
        result = profile.extract_profile('Interior 100 x 0 x 7 mm.')
        self.assertIsNone(result['interior_mm'])
        self.assertTrue(any(item['field'] == 'interior_mm' for item in result['unresolved']))

    def test_provenance_is_bound_to_original_text(self):
        first = profile.extract_profile('ECG', source='upload.txt')
        second = profile.extract_profile('EEG', source='upload.txt')
        self.assertNotEqual(first['provenance']['brief_revision'], second['provenance']['brief_revision'])
        self.assertEqual(first['provenance']['source'], 'upload.txt')
        self.assertEqual(first['provenance']['method'], 'explicit_text_rules')


if __name__ == '__main__':
    unittest.main()
