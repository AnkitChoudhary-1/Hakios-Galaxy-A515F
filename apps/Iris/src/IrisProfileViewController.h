// IrisProfileViewController.h - User Profile screen
#import <UIKit/UIKit.h>

@interface IrisProfileViewController : UIViewController

@property (nonatomic, copy) NSString *username;

- (instancetype)initWithUsername:(NSString *)username;

@end
