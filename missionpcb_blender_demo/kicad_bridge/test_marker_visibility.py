"""The toggle covers actual area flags as well as comment text."""
import unittest
from unittest.mock import Mock,patch
from kipy.board_types import BoardLayer
import widget_command
class MarkerVisibilityTests(unittest.TestCase):
 def test_hide_and_show_preserve_other_layers(self):
  layers={BoardLayer.BL_F_Cu,*widget_command.review_layers()}
  board=Mock();board.get_visible_layers.side_effect=lambda:list(layers)
  def update(values):layers.clear();layers.update(values)
  board.set_visible_layers.side_effect=update
  with patch.object(widget_command.bridge,'connect',return_value=board):
   self.assertIn('hidden',widget_command.run('hide review markers'))
   self.assertEqual(layers,{BoardLayer.BL_F_Cu})
   self.assertIn('visible',widget_command.run('show review markers'))
   self.assertEqual(layers,{BoardLayer.BL_F_Cu,*widget_command.review_layers()})
 def test_unconfirmed_toggle_is_not_reported_as_success(self):
  board=Mock();board.get_visible_layers.return_value=[BoardLayer.BL_F_Cu]
  with patch.object(widget_command.bridge,'connect',return_value=board):
   with self.assertRaisesRegex(ValueError,'did not confirm'):widget_command.run('show review markers')
if __name__=='__main__':unittest.main()
