// IrisCommentsViewController.h
#import <UIKit/UIKit.h>
#import "IrisData.h"

@interface IrisCommentsViewController : UIViewController

@property (nonatomic, strong, readonly) IrisPost *post;

- (instancetype)initWithPost:(IrisPost *)post;

@end
