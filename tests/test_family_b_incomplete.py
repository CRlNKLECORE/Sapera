import unittest
from sapera import cli

class FamilyBIncompleteTests(unittest.TestCase):
    def test_family_b_profiles_are_not_claimed_verified(self):
        db=cli.load_db()
        for b in db['builds'].values():
            if set(b.get('chds',[])) & {'a30b02','a30c02','a45a02'}:
                _,profile=cli.select_profile(b,'C')
                self.assertEqual('known_incomplete',profile['status'])
                with self.assertRaises(ValueError):
                    cli.authorize_profile('C',profile,allow_unverified=True,allow_incomplete=False)
                cli.authorize_profile('C',profile,allow_unverified=True,allow_incomplete=True)
